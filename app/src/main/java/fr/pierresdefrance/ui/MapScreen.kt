package fr.pierresdefrance.ui

import android.graphics.Color
import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Paint
import android.graphics.Typeface
import android.graphics.RectF
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.viewinterop.AndroidView
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import fr.pierresdefrance.domain.Bounds
import fr.pierresdefrance.domain.Position
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.maplibre.android.MapLibre
import org.maplibre.android.camera.CameraPosition
import org.maplibre.android.camera.CameraUpdateFactory
import org.maplibre.android.geometry.LatLng
import org.maplibre.android.maps.*
import org.maplibre.android.style.expressions.Expression.*
import org.maplibre.android.style.layers.*
import org.maplibre.android.style.layers.PropertyFactory.*
import org.maplibre.android.style.sources.*
import org.maplibre.geojson.*

private val emptyFeatures=FeatureCollection.fromFeatures(emptyArray<Feature>())

@Composable
fun MapScreen(state: DiscoveryState,vm: DiscoveryViewModel,active: Boolean) {
    val context=LocalContext.current
    val lifecycle=LocalLifecycleOwner.current.lifecycle
    val view=remember { MapLibre.getInstance(context); MapView(context,MapLibreMapOptions.createFromAttributes(context).textureMode(true)).apply { onCreate(null) } }
    var map by remember { mutableStateOf<MapLibreMap?>(null) }
    var style by remember { mutableStateOf<Style?>(null) }
    DisposableEffect(view) { onDispose { view.onDestroy() } }
    DisposableEffect(view,lifecycle,active) {
        var started=false; var resumed=false
        fun sync() {
            val needStart=active && lifecycle.currentState.isAtLeast(Lifecycle.State.STARTED)
            val needResume=active && lifecycle.currentState.isAtLeast(Lifecycle.State.RESUMED)
            if(resumed && !needResume) { view.onPause(); resumed=false }
            if(started && !needStart) { view.onStop(); started=false }
            if(!started && needStart) { view.onStart(); started=true }
            if(!resumed && needResume) { view.onResume(); resumed=true }
        }
        val observer=LifecycleEventObserver { _,_ -> sync() }
        lifecycle.addObserver(observer); sync()
        onDispose { lifecycle.removeObserver(observer); if(resumed) view.onPause(); if(started) view.onStop() }
    }
    AndroidView(modifier=Modifier.fillMaxSize(),factory={ view })
    LaunchedEffect(view) {
        view.getMapAsync { instance ->
            map=instance
            instance.cameraPosition=CameraPosition.Builder().target(LatLng(46.6,2.4)).zoom(4.1).build()
            instance.uiSettings.isLogoEnabled=false
            instance.setStyle(Style.Builder().fromJson(BASE_STYLE)) { loaded ->
                view.addOnStyleImageMissingListener { id ->
                    id.removePrefix("count-").toIntOrNull()?.takeIf { id.startsWith("count-") && it > 1 }?.let { count ->
                        val bitmap=Bitmap.createBitmap(112,40,Bitmap.Config.ARGB_8888)
                        bitmap.density=160
                        val paint=Paint(Paint.ANTI_ALIAS_FLAG).apply {
                            color=Color.rgb(250,248,243); textSize=if(count<10000) 28f else 23f
                            typeface=Typeface.create(Typeface.SANS_SERIF,Typeface.BOLD); textAlign=Paint.Align.CENTER
                        }
                        Canvas(bitmap).drawText(count.toString(),56f,20f-(paint.ascent()+paint.descent())/2,paint)
                        loaded.addImage(id,bitmap)
                        bitmap.recycle()
                    }
                }
                installLayers(loaded); style=loaded
                fun idle() {
                    val b=instance.projection.visibleRegion.latLngBounds
                    vm.viewport(Bounds(b.latitudeSouth,b.longitudeWest,b.latitudeNorth,b.longitudeEast),instance.cameraPosition.zoom)
                }
                instance.addOnCameraIdleListener { idle() }; idle()
                instance.addOnMapClickListener { point ->
                    val px=instance.projection.toScreenLocation(point); val r=20*context.resources.displayMetrics.density
                    val features=instance.queryRenderedFeatures(RectF(px.x-r,px.y-r,px.x+r,px.y+r),"major-points","individual","clusters","cells")
                    val feature=features.firstOrNull()
                    if(feature!=null) {
                        val p=feature.geometry() as? Point
                        when {
                            feature.hasProperty("cluster_id") -> {
                                val source=loaded.getSourceAs<GeoJsonSource>("points")
                                val z=source?.getClusterExpansionZoom(feature)?.toDouble() ?: instance.cameraPosition.zoom+2
                                if(p!=null) instance.animateCamera(CameraUpdateFactory.newLatLngZoom(LatLng(p.latitude(),p.longitude()),z))
                            }
                            feature.getNumberProperty("count")?.toInt()?.let { it>1 }==true -> {
                                if(p!=null) instance.animateCamera(CameraUpdateFactory.newLatLngZoom(LatLng(p.latitude(),p.longitude()),instance.cameraPosition.zoom+2))
                            }
                            feature.hasProperty("id") -> {
                                vm.select(feature.getStringProperty("id").toLong())
                            }
                        }
                    }
                    feature!=null
                }
            }
        }
    }
    LaunchedEffect(style,state.map) {
        val loaded=style ?: return@LaunchedEffect
        val result=state.map ?: return@LaunchedEffect
        val collections=withContext(Dispatchers.Default) {
            val points=mutableListOf<Feature>(); val majors=mutableListOf<Feature>(); val cells=mutableListOf<Feature>()
            result.items.sortedBy { it.importance }.forEach { item ->
                val feature=Feature.fromGeometry(Point.fromLngLat(item.longitude,item.latitude)).apply {
                    addStringProperty("id",item.id.toString()); addNumberProperty("importance",item.importance); addNumberProperty("count",item.count)
                    addNumberProperty("level",item.visualLevel)
                }
                when {
                    result.aggregated -> cells.add(feature)
                    item.visualLevel==3 -> majors.add(feature)
                    else -> points.add(feature)
                }
            }
            listOf(points,majors,cells).map { FeatureCollection.fromFeatures(it) }
        }
        withContext(Dispatchers.Main.immediate) {
            listOf("points","majors","aggregates").forEachIndexed { i,id -> loaded.getSourceAs<GeoJsonSource>(id)?.setGeoJson(collections[i]) }
        }
    }
    LaunchedEffect(style,state.position) {
        val p=state.position
        style?.getSourceAs<GeoJsonSource>("position")?.setGeoJson(if(p==null) emptyFeatures else
            FeatureCollection.fromFeatures(arrayOf(Feature.fromGeometry(Point.fromLngLat(p.longitude,p.latitude)))))
    }
    LaunchedEffect(style,state.exploration) {
        val p=state.exploration?.position
        style?.getSourceAs<GeoJsonSource>("exploration")?.setGeoJson(if(p==null) emptyFeatures else
            FeatureCollection.fromFeatures(arrayOf(Feature.fromGeometry(Point.fromLngLat(p.longitude,p.latitude)))))
    }
    LaunchedEffect(style,state.selectedId,state.detail) {
        val m=state.detail
        style?.getSourceAs<GeoJsonSource>("selection")?.setGeoJson(if(m?.latitude==null || m.longitude==null) emptyFeatures else
            FeatureCollection.fromFeatures(arrayOf(Feature.fromGeometry(Point.fromLngLat(m.longitude,m.latitude)))))
    }
    LaunchedEffect(style,state.focusSerial) {
        state.focus?.let { map?.animateCamera(CameraUpdateFactory.newLatLngZoom(LatLng(it.latitude,it.longitude),state.focusZoom)) }
    }
}



private fun installLayers(style: Style) {
    style.addSource(GeoJsonSource("points",emptyFeatures,GeoJsonOptions().withCluster(true).withClusterRadius(42).withClusterMaxZoom(15)))
    for(id in listOf("majors","aggregates","position","selection","exploration")) style.addSource(GeoJsonSource(id,emptyFeatures))
    val ink=Color.rgb(62,94,101); val paper=Color.rgb(250,248,243)
    fun radius()=step(get("level"),literal(5),stop(2,7),stop(3,9))
    fun ratingColor()=match(get("level"),literal(1),literal("#F7B955"),literal(2),literal("#64B5F6"),literal(3),literal("#8E3A8A"),literal("#3E5E65"))
    val cellColor=switchCase(eq(get("count"),literal(1)),ratingColor(),literal("#3E5E65"))
    style.addLayer(CircleLayer("cells","aggregates").withProperties(circleColor(cellColor),circleRadius(step(get("count"),literal(7),stop(2,17),stop(100,22),stop(1000,26))),circleStrokeWidth(2f),circleStrokeColor(paper)))
    style.addLayer(CircleLayer("clusters","points").withFilter(has("point_count")).withProperties(circleColor(ink),circleRadius(19f),circleStrokeWidth(2f),circleStrokeColor(paper)))
    style.addLayer(CircleLayer("individual","points").withFilter(not(has("point_count"))).withProperties(circleColor(ratingColor()),circleRadius(radius()),circleStrokeColor(paper),circleStrokeWidth(2f)))
    // Render important monuments last, outside the ordinary cluster source.
    style.addLayer(CircleLayer("major-points","majors").withProperties(circleColor(ratingColor()),circleRadius(9f),circleStrokeColor(paper),circleStrokeWidth(2f)))
    for((id,source,field) in listOf(Triple("cell-labels","aggregates","count"),Triple("cluster-labels","points","point_count"))) {
        style.addLayer(SymbolLayer(id,source).withFilter(gt(get(field),literal(1))).withProperties(
            iconImage(concat(literal("count-"),toString(get(field)))),iconSize(.5f),iconAllowOverlap(true),iconIgnorePlacement(true)))
    }
    style.addLayer(CircleLayer("selected","selection").withProperties(circleColor(Color.TRANSPARENT),circleRadius(15f),circleStrokeColor(Color.rgb(156,89,68)),circleStrokeWidth(4f)))
    style.addLayer(CircleLayer("user-position","position").withProperties(circleColor(Color.rgb(63,128,192)),circleRadius(7f),circleStrokeColor(Color.WHITE),circleStrokeWidth(3f)))
    style.addLayer(CircleLayer("exploration-center","exploration").withProperties(circleColor(Color.rgb(156,89,68)),circleRadius(9f),circleStrokeColor(paper),circleStrokeWidth(3f)))
}

private const val BASE_STYLE="""{"version":8,"sources":{"osm":{"type":"raster","tiles":["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],"tileSize":256,"maxzoom":19,"attribution":"© OpenStreetMap contributors"}},"layers":[{"id":"paper","type":"background","paint":{"background-color":"#F2F0EA"}},{"id":"base","type":"raster","source":"osm","paint":{"raster-saturation":-0.8,"raster-opacity":0.85}}]}"""


