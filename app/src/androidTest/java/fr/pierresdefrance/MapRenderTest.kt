package fr.pierresdefrance

import android.graphics.Bitmap
import android.graphics.RectF
import android.graphics.Color
import android.os.SystemClock
import android.util.Log
import android.view.View
import android.view.ViewGroup
import android.view.Window
import android.view.FrameMetrics
import androidx.test.core.app.ActivityScenario
import androidx.test.platform.app.InstrumentationRegistry
import fr.pierresdefrance.ui.*
import org.junit.Assert.*
import org.junit.Test
import org.maplibre.android.maps.MapView
import org.maplibre.android.maps.MapLibreMap
import org.maplibre.android.camera.CameraUpdateFactory
import org.maplibre.android.geometry.LatLng
import java.io.File
import java.util.Collections
import org.maplibre.geojson.Point

class MapRenderTest {
    @Test fun fullCatalogueRendersAtNationalAndCityScales() {
        val instrumentation=InstrumentationRegistry.getInstrumentation()
        val scenario=ActivityScenario.launch(MainActivity::class.java)
        var map: MapLibreMap?=null; var view: MapView?=null
        val frames=Collections.synchronizedList(mutableListOf<Long>())
        val listener=Window.OnFrameMetricsAvailableListener { _,m,_ -> frames.add(m.getMetric(FrameMetrics.TOTAL_DURATION)) }
        fun find(v: View): MapView? {
            if(v is MapView) return v
            if(v is ViewGroup) for(i in 0 until v.childCount) find(v.getChildAt(i))?.let { return it }
            return null
        }
        fun until(label: String,condition: ()->Boolean) {
            val end=SystemClock.elapsedRealtime()+30000
            while(SystemClock.elapsedRealtime()<end) {
                var yes=false
                instrumentation.runOnMainSync { yes=condition() }
                if(yes) return
                SystemClock.sleep(100)
            }
            fail("Timed out: $label")
        }
        fun features(vararg layers: String)=map!!.queryRenderedFeatures(RectF(0f,0f,view!!.width.toFloat(),view!!.height.toFloat()),*layers)
        fun screenshot(name: String) {
            val context=instrumentation.targetContext
            val directory=File(context.getExternalFilesDir(null),"screenshots").apply { mkdirs() }
            instrumentation.uiAutomation.takeScreenshot()?.let { b -> File(directory,"$name.png").outputStream().use { b.compress(Bitmap.CompressFormat.PNG,100,it) }; b.recycle() }
            instrumentation.uiAutomation.executeShellCommand("cp ${File(directory,"$name.png").absolutePath} /sdcard/Download/heritage-$name.png").close()
        }
        try {
            scenario.onActivity { it.window.addOnFrameMetricsAvailableListener(listener,android.os.Handler(android.os.Looper.getMainLooper())) }
            until("MapView") {
                if(view==null) scenario.onActivity { activity -> view=find(activity.window.decorView); view?.getMapAsync { map=it } }
                map?.style?.isFullyLoaded==true
            }
            until("national cluster labels") { features("cell-labels").isNotEmpty() }
            SystemClock.sleep(1000)
            val centers=mutableListOf<android.graphics.PointF>()
            val scale=instrumentation.targetContext.resources.displayMetrics.density
            instrumentation.runOnMainSync {
                val offset=IntArray(2); view!!.getLocationOnScreen(offset)
                features("cells").filter { it.getNumberProperty("count").toInt()>=10 }.forEach { feature ->
                    val p=feature.geometry() as Point
                    val screen=map!!.projection.toScreenLocation(LatLng(p.latitude(),p.longitude()))
                    centers.add(android.graphics.PointF(screen.x+offset[0],screen.y+offset[1]))
                }
            }
            val pixels=instrumentation.uiAutomation.takeScreenshot()!!
            val visibleNumbers=centers.count { p ->
                if(p.x<30*scale || p.x>pixels.width-30*scale || p.y<pixels.height*.25 || p.y>pixels.height*.8) false
                else {
                    var lightPixels=0
                    for(x in (p.x-10*scale).toInt()..(p.x+10*scale).toInt())
                        for(y in (p.y-6*scale).toInt()..(p.y+6*scale).toInt()) {
                            val color=pixels.getPixel(x,y)
                            if(Color.red(color)>230 && Color.green(color)>230 && Color.blue(color)>220) lightPixels++
                        }
                    lightPixels>40
                }
            }
            pixels.recycle()
            assertTrue("At least three counters must contain visible light number pixels; found $visibleNumbers",visibleNumbers>=3)
            screenshot("carte-france")
            val places=listOf(Triple("paris",LatLng(48.8566,2.3522),12.5),Triple("bordeaux",LatLng(44.8378,-.5792),13.0),Triple("rural",LatLng(44.1,3.4),11.0))
            for((name,center,zoom) in places) {
                instrumentation.runOnMainSync { map!!.moveCamera(CameraUpdateFactory.newLatLngZoom(center,zoom)) }
                SystemClock.sleep(700)
                until("$name points") { features("individual","major-points","clusters").isNotEmpty() }
                screenshot("carte-$name")
                instrumentation.runOnMainSync { Log.i("MapRenderBenchmark","$name visibleFeatures=${features("individual","major-points","clusters").size}") }
            }
            instrumentation.runOnMainSync { map!!.moveCamera(CameraUpdateFactory.newLatLngZoom(LatLng(48.8566,2.3522),12.5)) }
            SystemClock.sleep(1000); frames.clear()
            instrumentation.runOnMainSync { map!!.animateCamera(CameraUpdateFactory.newLatLngZoom(LatLng(48.859,2.347),17.0),2200) }
            SystemClock.sleep(3000)
            val measured=synchronized(frames) { frames.toList().sorted() }
            assertTrue(measured.isNotEmpty())
            Log.i("MapRenderBenchmark","ParisZoom windowFrames=${measured.size} p95_ms=${measured[(measured.size*.95).toInt().coerceAtMost(measured.lastIndex)]/1e6}")
            screenshot("carte-paris-quartier")
        } finally {
            scenario.onActivity { it.window.removeOnFrameMetricsAvailableListener(listener) }
            scenario.close()
        }
    }
}
