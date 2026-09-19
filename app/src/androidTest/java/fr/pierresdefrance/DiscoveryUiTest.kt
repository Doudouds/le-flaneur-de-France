package fr.pierresdefrance

import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.v2.createAndroidComposeRule
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import android.os.ParcelFileDescriptor
import android.content.Context
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class DiscoveryUiTest {
    @get:Rule val ui=createAndroidComposeRule<MainActivity>()
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

