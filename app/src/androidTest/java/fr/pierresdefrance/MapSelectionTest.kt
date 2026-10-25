package fr.pierresdefrance

import android.view.View
import android.view.ViewGroup
import android.view.InputDevice
import android.view.MotionEvent
import android.graphics.RectF
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.v2.createAndroidComposeRule
import androidx.lifecycle.ViewModelProvider
import androidx.test.espresso.Espresso.onView
import androidx.test.espresso.action.GeneralClickAction
import androidx.test.espresso.action.Press
import androidx.test.espresso.action.Tap
import androidx.test.espresso.matcher.ViewMatchers.isAssignableFrom
import fr.pierresdefrance.data.*
import fr.pierresdefrance.domain.Position
import fr.pierresdefrance.ui.DiscoveryViewModel
import kotlinx.coroutines.runBlocking
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.maplibre.android.camera.CameraUpdateFactory
import org.maplibre.android.geometry.LatLng
import org.maplibre.android.maps.MapLibreMap
import org.maplibre.android.maps.MapView

class MapSelectionTest {
    @get:Rule val ui=createAndroidComposeRule<MainActivity>()

    @Test fun tappingSharedCoordinatesLetsEveryNoticeBeSelected() {
        val position=Position(45.90314448293821,5.179352397311684)
        val db=MonumentDatabase.open(ui.activity)
        val choices=try {
            val id=db.query("SELECT id FROM monuments WHERE latitude=? AND longitude=? LIMIT 1",
                arrayOf(position.latitude,position.longitude)).use { assertTrue(it.moveToFirst()); it.getLong(0) }
            runBlocking { MonumentRepository(db).mapChoices(id) }
        } finally { db.close() }
        assertTrue("The fixture must contain distinct notices sharing a point",choices.size>1)
        assertEquals(choices.size,choices.map { it.reference }.distinct().size)
        assertTrue(choices.any { it.address.isNotBlank() })
        lateinit var vm: DiscoveryViewModel
        var map: MapLibreMap?=null
        fun find(view: View): MapView? {
            if(view is MapView) return view
            if(view is ViewGroup) for(i in 0 until view.childCount) find(view.getChildAt(i))?.let { return it }
            return null
        }
        ui.waitUntil(30000) { ui.onAllNodesWithText("Adresse ou ville").fetchSemanticsNodes().isNotEmpty() }
        ui.runOnUiThread {
            vm=ViewModelProvider(ui.activity)[DiscoveryViewModel::class.java]
            find(ui.activity.window.decorView)!!.getMapAsync { map=it }
        }
        ui.waitUntil(10000) { map!=null }
        ui.runOnUiThread { map!!.moveCamera(CameraUpdateFactory.newLatLngZoom(LatLng(position.latitude,position.longitude),17.0)) }
        ui.waitUntil(15000) { vm.state.value.map?.items?.count { it.latitude==position.latitude && it.longitude==position.longitude }==choices.size }
        ui.waitUntil(15000) {
            var rendered=false
            ui.runOnUiThread {
                val p=map!!.projection.toScreenLocation(LatLng(position.latitude,position.longitude))
                rendered=map!!.queryRenderedFeatures(RectF(p.x-2,p.y-2,p.x+2,p.y+2),"individual","major-points")
                    .map { it.getStringProperty("id") }.distinct().size==choices.size
            }
            rendered
        }
        for(choice in listOf(choices.first(),choices.last())) {
            // Exercise the actual map click listener, rather than calling the view model directly.
            onView(isAssignableFrom(MapView::class.java)).perform(GeneralClickAction(Tap.SINGLE,{ view ->
                val offset=IntArray(2); view.getLocationOnScreen(offset)
                val point=map!!.projection.toScreenLocation(LatLng(position.latitude,position.longitude))
                floatArrayOf(offset[0]+point.x,offset[1]+point.y)
            },Press.FINGER,InputDevice.SOURCE_TOUCHSCREEN,MotionEvent.BUTTON_PRIMARY))
            ui.waitUntil(10000) { vm.state.value.mapChoices.size==choices.size }
            ui.onNodeWithText("${choices.size} monuments à cet endroit").assertIsDisplayed()
            ui.onNode(hasScrollToNodeAction()).performScrollToNode(hasText(choice.reference))
            ui.onNodeWithText(choice.reference).performClick()
            ui.waitUntil(10000) { vm.state.value.detail?.id==choice.id }
            assertTrue(vm.state.value.mapChoices.isEmpty())
            ui.onNodeWithText("Itinéraire").assertIsEnabled()
            ui.runOnUiThread { vm.dismiss() }
            ui.waitUntil(10000) { vm.state.value.selectedId==null }
        }
        val singleDb=MonumentDatabase.open(ui.activity)
        val eiffel=try { runBlocking {
            val repo=MonumentRepository(singleDb)
            repo.detail(repo.search("PA00088801").single().id)!!
        } } finally { singleDb.close() }
        ui.runOnUiThread { vm.selectOnMap(eiffel.id) }
        ui.waitUntil(10000) { vm.state.value.detail?.id==eiffel.id }
        assertTrue(vm.state.value.mapChoices.isEmpty())
    }
}
