package ro.unihack.smartwaste

import kotlinx.coroutines.test.runTest
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.Assert.*
import org.junit.Test
import ro.unihack.smartwaste.api.api
import ro.unihack.smartwaste.auth.TokenStore
import ro.unihack.smartwaste.model.*
import ro.unihack.smartwaste.navigation.routesFor

class ContractTest {
    @Test fun fillThresholdsAndUnknown() {
        assertEquals(FillState.UNKNOWN, fillState(null))
        assertEquals(FillState.NORMAL, fillState(0))
        assertEquals(FillState.NORMAL, fillState(59))
        assertEquals(FillState.WARNING, fillState(60))
        assertEquals(FillState.WARNING, fillState(79))
        assertEquals(FillState.FULL, fillState(80))
        assertEquals(FillState.FULL, fillState(100))
    }
    @Test fun navigationIsRoleScoped() {
        assertFalse(routesFor("Resident").any { it.first == "users" || it.first == "map" })
        assertTrue(routesFor("Company").any { it.first == "map" })
        assertTrue(routesFor("Admin").any { it.first == "users" })
        assertTrue(routesFor("Unknown").isEmpty())
    }
    @Test fun bearerAndIncidentJsonContract() = runTest {
        MockWebServer().use { server ->
            server.enqueue(MockResponse().setBody("""[{"bin_id":"BIN_001","name":"Test","fill_level":85,"recorded_at":null}]"""))
            val store = object : TokenStore { override var token: String? = "session-token" }
            val service = api(server.url("/").toString(), store)
            assertEquals(85, service.bins().first().fill_level)
            val request = server.takeRequest()
            assertEquals("/api/v1/bins", request.path)
            assertEquals("Bearer session-token", request.getHeader("Authorization"))
            assertNull(request.getHeader("X-API-Key"))
            server.enqueue(MockResponse().setResponseCode(201).setBody("""{"id":1,"bin_id":"BIN_001","user_id":1,"category":"damaged","comment":"Broken","status":"open","created_at":"now","updated_at":"now"}"""))
            service.report(IncidentInput("BIN_001", "damaged", "Broken"))
            assertTrue(server.takeRequest().body.readUtf8().contains("\"comment\":\"Broken\""))
        }
    }
    @Test fun logoutAndPasswordAcceptNoContent() = runTest {
        MockWebServer().use { server ->
            val store = object : TokenStore { override var token: String? = "session-token" }
            val service = api(server.url("/").toString(), store)
            server.enqueue(MockResponse().setResponseCode(204))
            service.logout()
            assertEquals("/api/v1/auth/logout", server.takeRequest().path)
            server.enqueue(MockResponse().setResponseCode(204))
            service.password(PasswordChange("old", "newpassword"))
            assertEquals("/api/v1/auth/password", server.takeRequest().path)
        }
    }
}
