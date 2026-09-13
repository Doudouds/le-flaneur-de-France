package fr.pierresdefrance.data

import fr.pierresdefrance.domain.Position
import kotlinx.coroutines.*
import okhttp3.*
import okhttp3.HttpUrl.Companion.toHttpUrl
import org.json.JSONObject
import java.io.IOException
import java.util.concurrent.TimeUnit
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException

data class AddressPlace(val label: String,val context: String,val position: Position,val type: String) {
    val zoom: Double get()=if(type=="municipality") 12.5 else 15.5
}

fun interface AddressSearch { suspend fun search(query: String): List<AddressPlace> }

/** Debounced address suggestions: no GPS is sent, no address history is stored. */
class IgnAddressSearch: AddressSearch {
    private val client=OkHttpClient.Builder().callTimeout(12,TimeUnit.SECONDS).build()
    override suspend fun search(query: String): List<AddressPlace> = coroutineScope {
        // A short place prefix should suggest towns as well as similarly named streets.
        if(query.trim().matches(Regex("[\\p{L}-]{3,6}")) && query.lowercase() !in setOf("rue","avenue","route","chemin","impasse","place","quai")) {
            val general=async { request(query) }
            val towns=async {
                try { request(query,"municipality") }
                catch(e: CancellationException) { throw e }
                catch(_: Exception) { emptyList() }
            }
            (towns.await().take(2)+general.await()).distinctBy { it.label to it.position }.take(5)
        } else request(query)
    }
    private suspend fun request(query: String,type: String?=null): List<AddressPlace> = withContext(Dispatchers.IO) {
        val url="https://data.geopf.fr/geocodage/search".toHttpUrl().newBuilder()
            .addQueryParameter("q",query.trim()).addQueryParameter("index","address")
            .addQueryParameter("limit","5").addQueryParameter("autocomplete","1")
            .apply { if(type!=null) addQueryParameter("type",type) }.build()
        val call=client.newCall(Request.Builder().url(url).header("User-Agent",HERITAGE_USER_AGENT).build())
        val body=suspendCancellableCoroutine<String> { continuation ->
            continuation.invokeOnCancellation { call.cancel() }
            call.enqueue(object: Callback {
                override fun onFailure(call: Call,e: IOException) {
                    if(continuation.isActive) continuation.resumeWithException(e)
                }
                override fun onResponse(call: Call,response: Response) {
                    response.use {
                        try {
                            if(!it.isSuccessful) throw IOException("Geocoder HTTP ${it.code}")
                            val text=it.body?.string() ?: throw IOException("Empty geocoder response")
                            if(continuation.isActive) continuation.resume(text)
                        } catch(e: Exception) { if(continuation.isActive) continuation.resumeWithException(e) }
                    }
                }
            })
        }
        parse(body)
    }
    companion object {
        fun parse(json: String): List<AddressPlace> {
            val features=JSONObject(json).getJSONArray("features")
            return (0 until features.length()).mapNotNull { index ->
                val feature=features.optJSONObject(index) ?: return@mapNotNull null
                val geometry=feature.optJSONObject("geometry") ?: return@mapNotNull null
                if(geometry.optString("type")!="Point") return@mapNotNull null
                val coords=geometry.optJSONArray("coordinates") ?: return@mapNotNull null
                val lon=coords.optDouble(0); val lat=coords.optDouble(1)
                if(!lat.isFinite() || !lon.isFinite() || lat !in -90.0..90.0 || lon !in -180.0..180.0) return@mapNotNull null
                val properties=feature.optJSONObject("properties") ?: return@mapNotNull null
                val label=properties.optString("label").trim()
                if(label.isBlank()) return@mapNotNull null
                AddressPlace(label,properties.optString("context"),Position(lat,lon),properties.optString("type"))
            }.distinctBy { it.label to it.position }.take(5)
        }
    }
}
