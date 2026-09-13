package fr.pierresdefrance.data

import android.content.Context
import kotlinx.coroutines.*
import okhttp3.*
import okhttp3.HttpUrl.Companion.toHttpUrl
import org.json.JSONObject
import java.io.IOException
import java.net.URLDecoder
import java.util.concurrent.TimeUnit
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException

data class WikipediaDescription(val text: String,val title: String,val url: String,val revision: Long) {
    val source: String get()="Wikipédia — « $title » — contributeurs, CC BY-SA 4.0"+
        if(revision>0) " — version $revision" else ""
}

/** Only follows an existing catalogue association; a local description is always available. */
class WikipediaDescriptions(context: Context) {
    private val cache=context.getSharedPreferences("wikipedia-descriptions-v1",Context.MODE_PRIVATE)
    private val client=OkHttpClient.Builder().callTimeout(12,TimeUnit.SECONDS).build()
    suspend fun resolve(m: MonumentDetail): WikipediaDescription? = withContext(Dispatchers.IO) {
        val url=m.wikipediaUrl.toHttpUrlOrNullSafe() ?: return@withContext null
        if(url.host!="fr.wikipedia.org" || !url.encodedPath.startsWith("/wiki/")) return@withContext null
        val stored=runCatching { JSONObject(cache.getString(m.wikipediaUrl,"{}")!!) }.getOrDefault(JSONObject())
        val previous=fromCache(stored)
        if(stored.optLong("expires")>System.currentTimeMillis()) return@withContext previous
        val title=URLDecoder.decode(url.encodedPath.removePrefix("/wiki/").replace("+","%2B"),"UTF-8").replace('_',' ')
        val endpoint="https://fr.wikipedia.org/w/api.php".toHttpUrl().newBuilder()
        mapOf("action" to "query","format" to "json","formatversion" to "2","redirects" to "1",
            "prop" to "extracts|pageprops|info","inprop" to "url","exintro" to "1",
            "explaintext" to "1","titles" to title,"maxlag" to "5").forEach { (key,value)->endpoint.addQueryParameter(key,value) }
        try {
            val call=client.newCall(Request.Builder().url(endpoint.build()).header("User-Agent",HERITAGE_USER_AGENT).build())
            val body=suspendCancellableCoroutine<String> { continuation ->
                continuation.invokeOnCancellation { call.cancel() }
                call.enqueue(object: Callback {
                    override fun onFailure(call: Call,e: IOException) { if(continuation.isActive) continuation.resumeWithException(e) }
                    override fun onResponse(call: Call,response: Response) {
                        response.use {
                            try {
                                if(!it.isSuccessful) throw IOException("Wikipedia HTTP ${it.code}")
                                val text=it.body?.string() ?: throw IOException("Empty Wikipedia response")
                                if(continuation.isActive) continuation.resume(text)
                            } catch(e: Exception) { if(continuation.isActive) continuation.resumeWithException(e) }
                        }
                    }
                })
            }
            val root=JSONObject(body)
            if(root.has("error")) throw IOException("Wikipedia API unavailable")
            val description=parse(root)
            ensureActive()
            val saved=JSONObject().put("expires",System.currentTimeMillis()+604_800_000L)
            description?.let { saved.put("text",it.text).put("title",it.title).put("url",it.url).put("revision",it.revision) }
            cache.edit().putString(m.wikipediaUrl,saved.toString()).apply()
            description
        } catch(e: CancellationException) { throw e }
        catch(_: Exception) {
            // Keep a previously downloaded introduction even when a refresh fails.
            stored.put("expires",System.currentTimeMillis()+300_000L)
            cache.edit().putString(m.wikipediaUrl,stored.toString()).apply()
            previous
        }
    }
    private fun String.toHttpUrlOrNullSafe()=runCatching { toHttpUrl() }.getOrNull()
    private fun fromCache(j: JSONObject): WikipediaDescription? = j.optString("text").takeIf { it.isNotBlank() }?.let {
        WikipediaDescription(it,j.optString("title"),j.optString("url"),j.optLong("revision"))
    }
    companion object {
        fun parse(root: JSONObject): WikipediaDescription? {
            val pages=root.optJSONObject("query")?.optJSONArray("pages") ?: return null
            if(pages.length()!=1) return null
            val page=pages.getJSONObject(0)
            if(page.has("missing") || page.optInt("ns",-1)!=0 || page.optJSONObject("pageprops")?.has("disambiguation")==true) return null
            val text=page.optString("extract").trim()
            val url=page.optString("fullurl")
            if(text.isBlank() || !url.startsWith("https://fr.wikipedia.org/wiki/")) return null
            return WikipediaDescription(text,page.optString("title"),url,page.optLong("lastrevid"))
        }
    }
}
