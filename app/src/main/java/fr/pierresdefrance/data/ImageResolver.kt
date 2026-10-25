package fr.pierresdefrance.data

import android.content.Context
import android.net.Uri
import android.text.Html
import kotlinx.coroutines.*
import okhttp3.*
import org.json.JSONObject
import java.io.IOException
import java.util.concurrent.TimeUnit
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException

data class HeritageImage(val url: String,val page: String,val author: String,val license: String,val licenseUrl: String)
const val HERITAGE_USER_AGENT="LesPierresDeFrance/0.3 (Android; heritage reference lookup)"

/** Adaptation of the Flâneur's Commons resolver: exact reference, explicit rights, no name fallback. */
class ImageResolver(context: Context,private val calls: Call.Factory=OkHttpClient.Builder()
    .connectTimeout(8,TimeUnit.SECONDS).readTimeout(8,TimeUnit.SECONDS).callTimeout(12,TimeUnit.SECONDS).build()) {
    private val cache=context.getSharedPreferences("commons-metadata-v1",Context.MODE_PRIVATE)
    suspend fun resolve(m: MonumentDetail): HeritageImage? = withContext(Dispatchers.IO) {
        if(m.imageUrl.isNotBlank() && m.imageLicense.isNotBlank()) return@withContext HeritageImage(m.imageUrl,m.imagePageUrl,m.imageAuthor,m.imageLicense,m.imageLicenseUrl)
        val stored=runCatching { JSONObject(cache.getString(m.reference,"{}")!!) }.getOrDefault(JSONObject())
        if(stored.optLong("expires")>System.currentTimeMillis()) return@withContext fromJson(stored)
        val params=mapOf("action" to "query","format" to "json","generator" to "search",
            "gsrsearch" to "insource:\"${m.reference}\"","gsrnamespace" to "6","gsrlimit" to "3",
            "prop" to "imageinfo|revisions","iiprop" to "url|mime|extmetadata","iiurlwidth" to "900",
            "rvprop" to "content","rvslots" to "main")
        val address="https://commons.wikimedia.org/w/api.php?"+params.entries.joinToString("&") { "${it.key}=${Uri.encode(it.value)}" }
        var failed=false
        val result=try {
                val call=calls.newCall(Request.Builder().url(address).header("User-Agent",HERITAGE_USER_AGENT).build())
                val body=suspendCancellableCoroutine<String> { continuation ->
                    continuation.invokeOnCancellation { call.cancel() }
                    call.enqueue(object: Callback {
                        override fun onFailure(call: Call,e: IOException) {
                            if(continuation.isActive) continuation.resumeWithException(e)
                        }
                        override fun onResponse(call: Call,response: Response) {
                            response.use {
                                try {
                                    if(!it.isSuccessful) throw IOException("Commons HTTP ${it.code}")
                                    val text=it.body?.string() ?: throw IOException("Empty Commons response")
                                    if(continuation.isActive) continuation.resume(text)
                                } catch(e: Exception) { if(continuation.isActive) continuation.resumeWithException(e) }
                            }
                        }
                    })
                }
                val root=JSONObject(body)
                check(!root.has("error"))
                val pages=root.optJSONObject("query")?.optJSONObject("pages")
                pages?.keys()?.asSequence()?.mapNotNull { key ->
                    val page=pages.getJSONObject(key)
                    val content=page.optJSONArray("revisions")?.optJSONObject(0)?.optJSONObject("slots")?.optJSONObject("main")?.optString("*").orEmpty()
                    val refs=Regex("PA[0-9AB]{8}").findAll(content).map { it.value }.toSet()
                    if(refs!=setOf(m.reference)) return@mapNotNull null
                    val info=page.optJSONArray("imageinfo")?.optJSONObject(0) ?: return@mapNotNull null
                    if(info.optString("mime") !in setOf("image/jpeg","image/png","image/webp")) return@mapNotNull null
                    val meta=info.optJSONObject("extmetadata") ?: return@mapNotNull null
                    fun value(k: String)=Html.fromHtml(meta.optJSONObject(k)?.optString("value").orEmpty(),Html.FROM_HTML_MODE_LEGACY).toString().trim()
                    val license=value("LicenseShortName"); val lower=license.lowercase()
                    if(listOf("nc","nd","fair use","gfdl","copyright").any { lower.contains(it) }) return@mapNotNull null
                    if(!(lower.contains("cc0") || lower.contains("public domain") || Regex("cc[- ]by(?:[- ]sa)? [1-4]\\.0").containsMatchIn(lower))) return@mapNotNull null
                    val url=info.optString("thumburl")
                    if(!url.startsWith("https://")) return@mapNotNull null
                    HeritageImage(url,info.optString("descriptionurl"),value("Artist").ifBlank { value("Credit") },license,value("LicenseUrl"))
                }?.firstOrNull()
        } catch(e: CancellationException) { throw e }
        catch(_: Exception) { failed=true; null }
        ensureActive()
        val saved=JSONObject().put("expires",System.currentTimeMillis()+if(failed) 3_600_000L else 604_800_000L)
        result?.let { saved.put("url",it.url).put("page",it.page).put("author",it.author).put("license",it.license).put("licenseUrl",it.licenseUrl) }
        cache.edit().putString(m.reference,saved.toString()).apply()
        result
    }
    private fun fromJson(j: JSONObject): HeritageImage? = j.optString("url").takeIf { it.isNotBlank() }?.let {
        HeritageImage(it,j.optString("page"),j.optString("author"),j.optString("license"),j.optString("licenseUrl"))
    }
}
