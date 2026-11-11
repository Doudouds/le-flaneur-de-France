package fr.pierresdefrance.data

import android.content.res.AssetManager
import java.text.Collator
import java.util.Locale
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject

data class DiscoveryRegion(val code: String, val name: String)

internal class DiscoveryCatalogue(private val assets: AssetManager, private val dao: MonumentDao) {
    private val selection by lazy {
        val json = assets.open("discovery_selection.json").bufferedReader().use { JSONObject(it.readText()) }
        val array = json.getJSONArray("regions")
        val regions = (0 until array.length()).associate { index ->
            val region = array.getJSONObject(index)
            val references = region.getJSONArray("references")
            DiscoveryRegion(region.getString("code"), region.getString("name")) to
                List(references.length()) { references.getString(it) }
        }
        Selection(regions, json.getJSONObject("descriptions"))
    }

    suspend fun regions(): List<DiscoveryRegion> = withContext(Dispatchers.IO) {
        val french = Collator.getInstance(Locale.FRENCH)
        selection.regions.keys.sortedWith { first, second -> french.compare(first.name, second.name) }
    }

    suspend fun draw(regionCode: String?, previous: String?): MonumentDetail? = withContext(Dispatchers.IO) {
        val references = if (regionCode == null) selection.regions.values.flatten()
        else selection.regions.entries.firstOrNull { it.key.code == regionCode }?.value.orEmpty()
        for (reference in references.filterNot { it == previous }.shuffled()) {
            val monument = dao.detailByReference(reference) ?: continue
            val description = selection.descriptions.optJSONObject(reference) ?: return@withContext monument
            return@withContext monument.copy(description = description.getString("text"),
                descriptionSource = description.getString("source"))
        }
        null
    }

    private data class Selection(
        val regions: Map<DiscoveryRegion, List<String>>,
        val descriptions: JSONObject,
    )
}
