package fr.pierresdefrance

import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.v2.createAndroidComposeRule
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import android.os.ParcelFileDescriptor
import android.content.Context
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import androidx.lifecycle.ViewModelProvider
import fr.pierresdefrance.ui.DiscoveryViewModel
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class DiscoveryUiTest {
    @get:Rule val ui=createAndroidComposeRule<MainActivity>()

    @Test fun discoveryDrawPersistsAndHonorsTheSelectedRegion() {
        lateinit var vm: DiscoveryViewModel
        ui.runOnUiThread { vm = ViewModelProvider(ui.activity)[DiscoveryViewModel::class.java] }
        ui.waitUntil(30000) { !vm.state.value.loading }
        ui.onNode(hasText("Découvrir") and hasClickAction()).performClick()
        ui.waitUntil(15000) { vm.state.value.draw.detail != null }
        val first = vm.state.value.draw.detail!!.reference
        val assets = InstrumentationRegistry.getInstrumentation().targetContext.assets
        val regions = assets.open("discovery_selection.json").bufferedReader().use {
            JSONObject(it.readText()).getJSONArray("regions")
        }
        val references = (0 until regions.length()).associate { i ->
            val region = regions.getJSONObject(i)
            val entries = region.getJSONArray("references")
            region.getString("name") to List(entries.length()) { entries.getString(it) }
        }
        assertEquals(18, references.size)
        assertEquals(2000, references.values.flatten().toSet().size)
        assertTrue(first in references.values.flatten())
        ui.onNodeWithText("Itinéraire").performScrollTo().assertIsEnabled()
        ui.onNodeWithText("Aide").performClick()
        ui.onNode(hasText("Découvrir") and hasClickAction()).performClick()
        assertEquals(first, vm.state.value.draw.detail?.reference)

        ui.onNodeWithText("France entière").performClick()
        ui.onNodeWithText("Mayotte").performScrollTo().performClick()
        assertEquals(first, vm.state.value.draw.detail?.reference)
        ui.onNodeWithText("Tirer").performClick()
        ui.waitUntil(15000) { vm.state.value.draw.detail?.reference?.let { it != first } == true }
        val second = vm.state.value.draw.detail!!.reference
        assertTrue(second in references.getValue("Mayotte"))
        ui.onNodeWithText("Tirer").performClick()
        ui.waitUntil(15000) { vm.state.value.draw.detail?.reference?.let { it != second } == true }
        assertNotEquals(second, vm.state.value.draw.detail?.reference)
        assertTrue(vm.state.value.draw.detail?.reference in references.getValue("Mayotte"))
    }

    @Test fun nationalSearchAndDetailWithoutLocation() {
        ui.waitUntil(30000) { ui.onAllNodesWithText("Adresse ou ville").fetchSemanticsNodes().isNotEmpty() }
        ui.onNodeWithText("Liste").performClick()
        ui.onNodeWithText("Rechercher un monument").performTextInput("Chambord")
        ui.waitUntil(15000) { ui.onAllNodesWithText("Domaine de Chambord").fetchSemanticsNodes().isNotEmpty() }
        ui.onNodeWithText("Domaine de Chambord").performClick()
        ui.waitUntil(15000) { ui.onAllNodesWithText("Itinéraire").fetchSemanticsNodes().isNotEmpty() }
        ui.onNodeWithText("Itinéraire").assertIsEnabled()
        ui.onNodeWithText("Protection").assertExists()
        ui.onNodeWithText("Voir sur la carte").performScrollTo().performClick()
        ui.waitUntil(10000) { ui.onAllNodesWithText("Adresse ou ville").fetchSemanticsNodes().isNotEmpty() }
        ui.onNodeWithText("Liste").performClick()
        ui.onNodeWithContentDescription("Effacer la recherche").performClick()
        ui.onNodeWithText("Rechercher un monument").performTextInput("PA2A000001")
        ui.waitUntil(10000) { ui.onAllNodesWithText("Recherche dans toute la France").fetchSemanticsNodes().isNotEmpty() }
    }

    @Test fun eiffelHasThreeStarsInListAndDetail() {
        ui.waitUntil(30000) { ui.onAllNodesWithText("Adresse ou ville").fetchSemanticsNodes().isNotEmpty() }
        ui.onNodeWithText("Liste").performClick()
        ui.onNodeWithText("Rechercher un monument").performTextInput("PA00088801")
        ui.waitUntil(15000) { ui.onAllNodesWithText("Tour Eiffel").fetchSemanticsNodes().isNotEmpty() }
        ui.onNodeWithText("★★★").assertExists()
        ui.onNodeWithText("Tour Eiffel").performClick()
        ui.waitUntil(15000) { ui.onAllNodesWithText("Rayonnement").fetchSemanticsNodes().isNotEmpty() }
        ui.onNodeWithText("90").assertExists()
        ui.onNodeWithText("Rayonnement").assertExists()
        ui.onNodeWithText("Source du rayonnement ↗").performScrollTo().assertIsDisplayed()
    }

    @Test fun offlineSearchAndNoticeWithoutCoordinates() {
        val instrumentation=InstrumentationRegistry.getInstrumentation()
        fun shell(command: String): String = ParcelFileDescriptor.AutoCloseInputStream(
            instrumentation.uiAutomation.executeShellCommand(command)).bufferedReader().use { it.readText().trim() }
        val wifi=shell("settings get global wifi_on")
        val mobile=shell("settings get global mobile_data")
        try {
            shell("svc wifi disable"); shell("svc data disable")
            val connections=instrumentation.targetContext.getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
            ui.waitUntil(10000) { connections.activeNetwork?.let { connections.getNetworkCapabilities(it)?.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET) }!=true }
            ui.waitUntil(30000) { ui.onAllNodesWithText("Adresse ou ville").fetchSemanticsNodes().isNotEmpty() }
            ui.onNodeWithText("Liste").performClick()
            ui.onNodeWithText("Rechercher un monument").performTextInput("PA95000004")
            ui.waitUntil(15000) { ui.onAllNodesWithText("Croix de cimetière").fetchSemanticsNodes().isNotEmpty() }
            ui.onNodeWithText("Croix de cimetière").performClick()
            ui.waitUntil(15000) { ui.onAllNodesWithText("Itinéraire").fetchSemanticsNodes().isNotEmpty() }
            ui.onNodeWithText("Itinéraire").assertIsNotEnabled()
            ui.onNodeWithText("La position de ce monument n’est pas renseignée ou reste à vérifier.").assertExists()
            ui.onNodeWithText("Voir la fiche officielle POP ↗").performScrollTo().assertIsDisplayed()
        } finally {
            shell("svc wifi ${if(wifi=="1" || wifi=="2") "enable" else "disable"}")
            shell("svc data ${if(mobile=="1") "enable" else "disable"}")
        }
    }
}

