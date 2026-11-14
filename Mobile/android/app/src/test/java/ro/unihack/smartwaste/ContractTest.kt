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
    @Test fun navigationKeepsAllCheckpointsAcrossSegments() {
        val points = (0..10).map { 45.0 + it / 100.0 to 21.0 + it / 100.0 }
        val first = ro.unihack.smartwaste.ui.mapsSegmentUrl(points, 0)
        assertTrue(first.contains("destination=45.03,21.03"))
        assertTrue(first.contains("waypoints=45.0,21.0%7C45.01,21.01%7C45.02,21.02"))
        val last = ro.unihack.smartwaste.ui.mapsSegmentUrl(points, 8)
        assertTrue(last.contains("destination=45.1,21.1"))
        assertFalse(last.contains("45.07"))
    }
    @Test fun companyAndProofContracts() = runTest {
        MockWebServer().use { server ->
            val store = object : TokenStore { override var token: String? = "session-token" }
            val service = api(server.url("/").toString(), store)
            server.enqueue(MockResponse().setBody("""{"hq_latitude":45.0,"hq_longitude":21.0,"stops":[],"straight_line_meters":0,"skipped_bin_ids":["BIN_001"]}"""))
            assertEquals(listOf("BIN_001"), service.route().skipped_bin_ids)
            assertEquals("POST", server.takeRequest().method)
            server.enqueue(MockResponse().setBody("""{"sha256":"abc","signature":null,"network":"devnet","status":"prepared","explorer_url":null}"""))
            assertEquals("prepared", service.proof(5).status)
            assertEquals("/api/v1/incidents/5/proof", server.takeRequest().path)
            server.enqueue(MockResponse().setBody("""{"bin_id":"BIN_001","is_damaged":true}"""))
            service.damage("BIN_001", DamageInput(true))
            val request = server.takeRequest()
            assertEquals("PATCH", request.method)
            assertEquals("{\"damaged\":true}", request.body.readUtf8())
        }
    }
    @Test fun categoriesAreNotPercentages() {
        val bin = Bin("BIN_001", "Test", null, null, null, 85, null)
        assertEquals("85%", binLevelLabel(bin))
        assertEquals("Gol", binLevelLabel(bin.copy(fill_category = 1, fill_level = null)))
        assertEquals(FillState.NORMAL, binState(bin.copy(fill_category = 1)))
        assertEquals("Mediu", binLevelLabel(bin.copy(fill_category = 2)))
        assertEquals(FillState.WARNING, binState(bin.copy(fill_category = 2)))
        assertEquals("Plin", binLevelLabel(bin.copy(fill_category = 3)))
        assertEquals(FillState.FULL, binState(bin.copy(fill_category = 3, fill_level = null)))
        assertEquals("Deteriorat", binLevelLabel(bin.copy(fill_category = 4)))
        assertEquals(FillState.DAMAGED, binState(bin.copy(fill_category = 4, fill_level = 0)))
    }
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
