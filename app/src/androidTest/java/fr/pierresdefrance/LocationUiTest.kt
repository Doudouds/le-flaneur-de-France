package fr.pierresdefrance

import android.Manifest
import android.location.Location
import android.os.ParcelFileDescriptor
import android.os.SystemClock
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.v2.createAndroidComposeRule
import androidx.test.platform.app.InstrumentationRegistry
import androidx.test.rule.GrantPermissionRule
import com.google.android.gms.location.LocationServices
import com.google.android.gms.tasks.Tasks
import org.junit.Rule
import org.junit.Test
import java.util.concurrent.TimeUnit
import androidx.lifecycle.ViewModelProvider
import fr.pierresdefrance.data.AddressPlace
import fr.pierresdefrance.domain.Position
import fr.pierresdefrance.ui.DiscoveryViewModel
import org.junit.Assert.*

/** Tests the real location-to-map-to-list flow with an explicit simulated Paris fix. */
class LocationUiTest {
    @get:Rule(order=0) val permissions: GrantPermissionRule = GrantPermissionRule.grant(
        Manifest.permission.ACCESS_FINE_LOCATION,Manifest.permission.ACCESS_COARSE_LOCATION)
    @get:Rule(order=1) val ui=createAndroidComposeRule<MainActivity>()

    @Test fun locationRecentersAndShowsNearby() {
        val instrumentation=InstrumentationRegistry.getInstrumentation()
        fun shell(command: String)=ParcelFileDescriptor.AutoCloseInputStream(
            instrumentation.uiAutomation.executeShellCommand(command)).bufferedReader().use { it.readText() }
        val old=shell("appops get fr.pierresdefrance android:mock_location")
        val client=LocationServices.getFusedLocationProviderClient(instrumentation.targetContext)
        shell("appops set fr.pierresdefrance android:mock_location allow")
        try {
            Tasks.await(client.setMockMode(true),10,TimeUnit.SECONDS)
            val fix=Location("fused").apply {
                latitude=48.8566; longitude=2.3522; accuracy=5f
                time=System.currentTimeMillis(); elapsedRealtimeNanos=SystemClock.elapsedRealtimeNanos()
            }
            Tasks.await(client.setMockLocation(fix),10,TimeUnit.SECONDS)
            ui.waitUntil(30000) { ui.onAllNodesWithContentDescription("Recentrer sur ma position").fetchSemanticsNodes().isNotEmpty() }
            ui.onNodeWithContentDescription("Recentrer sur ma position").performClick()
            ui.waitUntil(20000) { ui.onAllNodesWithText("monuments à moins de",substring=true).fetchSemanticsNodes().isNotEmpty() }
            ui.onNodeWithText("monuments à moins de",substring=true).performClick()
            ui.waitUntil(10000) { ui.onAllNodesWithText("Autour de vous",substring=true).fetchSemanticsNodes().isNotEmpty() }
            ui.onNodeWithText("par distance",substring=true).assertIsDisplayed()
            ui.onNodeWithText("Rechercher un monument").performTextInput("Chambord")
            ui.waitUntil(10000) { ui.onAllNodesWithText("Domaine de Chambord").fetchSemanticsNodes().isNotEmpty() }
            ui.onNodeWithText("Recherche dans toute la France").assertIsDisplayed()
            lateinit var vm: DiscoveryViewModel
            val city=AddressPlace("Bordeaux","Gironde",Position(44.851939,-.587877),"municipality")
            ui.runOnUiThread {
                vm=ViewModelProvider(ui.activity)[DiscoveryViewModel::class.java]
                vm.usePlace(city)
            }
            ui.waitUntil(10000) { vm.state.value.nearby?.origin==city.position }
            ui.onNodeWithText("Autour de Bordeaux",substring=true).assertIsDisplayed()
            ui.runOnUiThread { vm.locate(center=false) }
            assertEquals(city,vm.state.value.exploration)
            ui.onNodeWithText("Carte").performClick()
            ui.onNodeWithContentDescription("Recentrer sur ma position").performClick()
            ui.waitUntil(15000) { vm.state.value.exploration==null && vm.state.value.nearby?.origin==Position(48.8566,2.3522) }
            assertEquals("",vm.state.value.addressQuery)
            assertEquals("",vm.state.value.query)
            ui.onNodeWithText("Liste").performClick()
            ui.onNodeWithText("Autour de vous",substring=true).assertIsDisplayed()
        } finally {
            Tasks.await(client.setMockMode(false),10,TimeUnit.SECONDS)
            val previous=Regex("(?:MOCK_LOCATION|mock_location): (allow|ignore|deny|default)").find(old)?.groupValues?.get(1) ?: "default"
            shell("appops set fr.pierresdefrance android:mock_location $previous")
        }
    }
}
