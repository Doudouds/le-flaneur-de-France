package fr.pierresdefrance.location

import android.content.res.AssetManager
import fr.pierresdefrance.domain.Position
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.maplibre.geojson.FeatureCollection
import org.maplibre.geojson.MultiPolygon
import org.maplibre.geojson.Point
import org.maplibre.geojson.Polygon

/** Resolves a GPS fix against the bundled administrative boundaries. */
internal class RegionLocator(private val assets: AssetManager) {
    private val boundaries by lazy {
        // AAPT decompresses .gz assets and strips the .gz suffix when packaging the APK.
        val json = assets.open("discovery_regions.geojson").bufferedReader().use { it.readText() }
        FeatureCollection.fromJson(json).features().orEmpty()
    }

    suspend fun codeAt(position: Position): String? = withContext(Dispatchers.IO) {
        boundaries.firstOrNull { feature ->
            when (val shape = feature.geometry()) {
                is Polygon -> contains(shape.coordinates(), position)
                is MultiPolygon -> shape.coordinates().any { contains(it, position) }
                else -> false
            }
        }?.getStringProperty("code")
    }

    private fun contains(rings: List<List<Point>>, position: Position): Boolean =
        rings.firstOrNull()?.let { inRing(it, position) } == true &&
            rings.drop(1).none { inRing(it, position) }

    private fun inRing(points: List<Point>, position: Position): Boolean {
        var inside = false
        var previous = points.lastOrNull() ?: return false
        for (current in points) {
            val y = current.latitude()
            val previousY = previous.latitude()
            if ((y > position.latitude) != (previousY > position.latitude)) {
                val crossing = current.longitude() +
                    (previous.longitude() - current.longitude()) * (position.latitude - y) / (previousY - y)
                if (position.longitude < crossing) inside = !inside
            }
            previous = current
        }
        return inside
    }
}
