import os
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select, delete
from sqlalchemy.exc import IntegrityError
from . import schemas as S
from .models import User, Bin, Assignment, Incident, Session, now
from .security import db, current_user, admin, passwords, dummy_hash, public_user, issue, revoke, digest, bearer
from .services import visible_bins, owned_bin, company, bin_json, latest_categories

router = APIRouter(prefix='/api/v1')


def commit(session):
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(409, 'Înregistrarea există deja sau relația nu este validă.') from None


@router.post('/auth/login', tags=['Authentication'])
def login(body: S.Login, request: Request, session=Depends(db)):
    # Per-account throttling works across clients; intentionally generic failure message.
    request.app.state.sw_limiter.check(body.username.lower())
    user = session.scalar(select(User).where(User.username == body.username))
    valid = passwords.verify(body.password, user.password_hash if user else dummy_hash)
    if not valid or not user or not user.active:
        raise HTTPException(401, 'Nume de utilizator sau parolă incorectă.')
    request.app.state.sw_limiter.clear(body.username.lower())
    return issue(session, user, int(os.getenv('SMARTWASTE_SESSION_HOURS', '12')))


@router.get('/auth/me', tags=['Authentication'])
def me(user=Depends(current_user)):
    return public_user(user)


@router.post('/auth/logout', status_code=204, tags=['Authentication'])
def logout(user=Depends(current_user), credentials=Depends(bearer), session=Depends(db)):
    session.execute(delete(Session).where(Session.token_hash == digest(credentials.credentials)))
    session.commit()
    return Response(status_code=204)


@router.post('/auth/password', status_code=204, tags=['Authentication'])
def change_password(body: S.PasswordChange, user=Depends(current_user), session=Depends(db)):
    if not passwords.verify(body.current_password, user.password_hash):
        raise HTTPException(400, 'Parola curentă este incorectă.')
    user.password_hash = passwords.hash(body.new_password)
    revoke(session, user.id)
    session.commit()
    return Response(status_code=204)


@router.get('/bins', tags=['Bins'])
def bins(request: Request, user=Depends(current_user), session=Depends(db)):
    rows = session.scalars(visible_bins(session, user)).all()
    categories = latest_categories(session, [b.bin_id for b in rows])
    measurements = request.app.state.sw_legacy.readings() if any(b.bin_id not in categories for b in rows) else {}
    return [bin_json(b, measurements, categories.get(b.bin_id)) for b in rows]


@router.post('/bins/{bin_id}/collections', tags=['Bins'])
def collect(bin_id: str, request: Request, user=Depends(current_user), session=Depends(db)):
    if user.role != 'Company':
        raise HTTPException(403, 'Doar compania responsabilă poate confirma colectarea.')
    owned_bin(session, user, bin_id)
    # No automatic retries: the legacy API has no idempotency key.
    return {'result': request.app.state.sw_legacy.collect(bin_id, user.username)}


@router.get('/incidents', tags=['Incidents'])
def incidents(user=Depends(current_user), session=Depends(db)):
    query = select(Incident)
    if user.role == 'Resident':
        query = query.where(Incident.user_id == user.id)
    elif user.role == 'Company':
        query = query.join(Bin).where(Bin.company_id == user.id)
    return session.scalars(query.order_by(Incident.created_at.desc())).all()


@router.post('/incidents', status_code=201, tags=['Incidents'])
def create_incident(body: S.IncidentCreate, user=Depends(current_user), session=Depends(db)):
    if user.role != 'Resident':
        raise HTTPException(403, 'Sesizările sunt create de locatari.')
    owned_bin(session, user, body.bin_id)
    incident = Incident(**body.model_dump(), user_id=user.id)
    session.add(incident)
    session.flush()
    from .proofs import prepare
    prepare(incident)
    commit(session)
    return incident


@router.patch('/incidents/{incident_id}', tags=['Incidents'])
def update_incident(incident_id: int, body: S.IncidentStatus, user=Depends(current_user), session=Depends(db)):
    if user.role != 'Company':
        raise HTTPException(403, 'Nu poți modifica statusul sesizării.')
    incident = session.get(Incident, incident_id)
    if not incident:
        raise HTTPException(404, 'Sesizare inexistentă.')
    owned_bin(session, user, incident.bin_id)
    incident.status, incident.updated_at = body.status, now()
    commit(session)
    return incident


@router.get('/admin/users', tags=['Administration'])
def users(_=Depends(admin), session=Depends(db)):
    return [public_user(u) for u in session.scalars(select(User).order_by(User.id))]


@router.post('/admin/users', status_code=201, tags=['Administration'])
def create_user(body: S.UserCreate, _=Depends(admin), session=Depends(db)):
    user = User(username=body.username, display_name=body.display_name,
                role=body.role, password_hash=passwords.hash(body.password))
    session.add(user)
    commit(session)
    return public_user(user)


@router.put('/admin/users/{user_id}', tags=['Administration'])
def edit_user(user_id: int, body: S.UserEdit, _=Depends(admin), session=Depends(db)):
    user = session.get(User, user_id)
    if not user or user.role == 'Admin':
        raise HTTPException(404, 'Cont Resident/Company inexistent.')
    user.display_name, user.active = body.display_name, body.active
    if body.password:
        user.password_hash = passwords.hash(body.password)
    revoke(session, user.id)
    commit(session)
    return public_user(user)


@router.post('/admin/bins', status_code=201, tags=['Administration'])
def create_bin(body: S.BinInput, request: Request, _=Depends(admin), session=Depends(db)):
    company(session, body.company_id)
    if session.get(Bin, body.bin_id):
        raise HTTPException(409, 'Tomberonul este deja înregistrat.')
    bin = Bin(**body.model_dump())
    session.add(bin)
    commit(session)
    return bin_json(bin, {})


@router.put('/admin/bins/{bin_id}', tags=['Administration'])
def edit_bin(bin_id: str, body: S.BinInput, _=Depends(admin), session=Depends(db)):
    bin = session.get(Bin, bin_id)
    if not bin:
        raise HTTPException(404, 'Tomberon inexistent.')
    if body.bin_id != bin_id:
        raise HTTPException(422, 'Identificatorul tomberonului nu poate fi schimbat.')
    company(session, body.company_id)
    for key, value in body.model_dump().items():
        setattr(bin, key, value)
    commit(session)
    return bin_json(bin, {})


@router.get('/admin/users/{user_id}/bins', tags=['Administration'])
def assigned(user_id: int, _=Depends(admin), session=Depends(db)):
    user = session.get(User, user_id)
    if not user or user.role != 'Resident':
        raise HTTPException(404, 'Locatar inexistent.')
    return list(session.scalars(select(Assignment.bin_id).where(Assignment.user_id == user_id)))


@router.put('/admin/users/{user_id}/bins', tags=['Administration'])
def assign(user_id: int, body: S.Assignments, _=Depends(admin), session=Depends(db)):
    user = session.get(User, user_id)
    if not user or user.role != 'Resident' or not user.active:
        raise HTTPException(404, 'Locatar activ inexistent.')
    ids = set(body.bin_ids)
    found = set(session.scalars(select(Bin.bin_id).where(Bin.bin_id.in_(ids))))
    if ids != found:
        raise HTTPException(422, 'Lista conține tomberoane inexistente.')
    session.execute(delete(Assignment).where(Assignment.user_id == user_id))
    session.add_all(Assignment(user_id=user_id, bin_id=b) for b in sorted(ids))
    commit(session)
    return sorted(ids)
