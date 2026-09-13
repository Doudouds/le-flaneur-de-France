package fr.pierresdefrance

import android.app.Application
import androidx.activity.compose.setContent
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.v2.createAndroidComposeRule
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import fr.pierresdefrance.data.*
import fr.pierresdefrance.domain.Position
import fr.pierresdefrance.ui.*
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import java.io.IOException
import kotlinx.coroutines.*

class AddressSearchTest {
    @get:Rule val ui=createAndroidComposeRule<MainActivity>()

    @Test fun cityStreetAndFailedSearchKeepTheChosenOrigin() {
        val city=AddressPlace("Bordeaux","33, Gironde",Position(44.851939,-.587877),"municipality")
        val street=AddressPlace("Rue Sainte-Catherine 33000 Bordeaux","33, Gironde",Position(44.8377,-.5745),"street")
        val queries=mutableListOf<String>()
        val service=AddressSearch { query ->
            queries.add(query)
            when(query) {
                "Bor"->listOf(city)
                "Rue Sainte Catherine Bordeaux"->listOf(street)
                "panne"->throw IOException("Simulated unavailable network")
                else->emptyList()
            }
        }
        lateinit var vm: DiscoveryViewModel
        ui.runOnUiThread {
            val factory=object: ViewModelProvider.Factory {
                @Suppress("UNCHECKED_CAST")
                override fun <T: ViewModel> create(modelClass: Class<T>): T =
                    DiscoveryViewModel(ui.activity.application as Application,service) as T
            }
            vm=ViewModelProvider(ui.activity,factory)["address-test",DiscoveryViewModel::class.java]
            ui.activity.setContent { HeritageTheme { DiscoveryApp(vm) } }
        }
        ui.waitUntil(30000) { ui.onAllNodesWithText("Adresse ou ville").fetchSemanticsNodes().isNotEmpty() }
        ui.onNodeWithText("Adresse ou ville").performTextInput("Bo")
        ui.runOnUiThread { assertTrue(queries.isEmpty()) }
        ui.onNodeWithText("Adresse ou ville").performTextInput("r")
        ui.waitUntil(10000) { ui.onAllNodesWithText("33, Gironde").fetchSemanticsNodes().isNotEmpty() }
        ui.onNodeWithText("33, Gironde").performClick()
        ui.waitUntil(15000) { vm.state.value.nearby!=null }
        assertEquals(city.position,vm.state.value.nearby!!.origin)
        assertEquals(12.5,vm.state.value.focusZoom,0.0)
        ui.onNodeWithText("Liste").performClick()
        ui.onNodeWithText("Autour de Bordeaux",substring=true).assertIsDisplayed()
        assertTrue(vm.state.value.rows.isNotEmpty())
        assertTrue(vm.state.value.rows.zipWithNext().all { (a,b)->a.distance!!<=b.distance!! })
        ui.runOnUiThread { vm.locate(center=false) }
        assertEquals(city,vm.state.value.exploration)
        ui.onNodeWithText("Carte").performClick()
        ui.onNodeWithText("Adresse ou ville").performTextReplacement("Rue Sainte Catherine Bordeaux")
        ui.waitUntil(10000) { ui.onAllNodesWithText(street.label).fetchSemanticsNodes().isNotEmpty() }
        ui.onNodeWithText(street.label).performClick()
        ui.waitUntil(10000) { vm.state.value.nearby?.origin==street.position }
        assertEquals(15.5,vm.state.value.focusZoom,0.0)
        for((query,message) in listOf("introuvable" to "Aucune adresse trouvée", "panne" to "Recherche d’adresse indisponible")) {
            ui.onNodeWithText("Adresse ou ville").performTextReplacement(query)
            ui.waitUntil(10000) { ui.onAllNodesWithText(message,substring=true).fetchSemanticsNodes().isNotEmpty() }
            assertEquals(street,vm.state.value.exploration)
            assertEquals(street.position,vm.state.value.nearby!!.origin)
        }
        assertEquals(listOf("Bor","Rue Sainte Catherine Bordeaux","introuvable","panne"),queries)
        ui.runOnUiThread { vm.editAddress("ancien"); vm.editAddress("no") }
        ui.waitForIdle()
        assertTrue(vm.state.value.addressResults.isEmpty())
        assertFalse(vm.state.value.addressSearching)
        assertEquals(4,queries.size)
    }

    @Test fun parsesIgnCoordinatesAndRejectsMalformedCandidates() {
        val result=IgnAddressSearch.parse("""{"features":[
            {"geometry":{"type":"Point","coordinates":[-0.58,44.85]},"properties":{"label":"Bordeaux","type":"municipality","context":"Gironde"}},
            {"geometry":{"type":"Point","coordinates":[-0.58,44.85]},"properties":{"label":"Bordeaux","type":"municipality"}},
            {"geometry":{"type":"Point","coordinates":[2,99]},"properties":{"label":"Invalid"}},
            {"geometry":{"type":"Point","coordinates":[2]},"properties":{"label":"Missing"}},
            {"geometry":{"type":"Polygon","coordinates":[]},"properties":{"label":"Not a point"}}
        ]}""")
        assertEquals(1,result.size)
        assertEquals(Position(44.85,-.58),result.single().position)
        assertEquals("Bordeaux",result.single().label)
        assertTrue(IgnAddressSearch.parse("""{"features":[]}""").isEmpty())
    }
}
