package fr.pierresdefrance

import android.content.Context
import androidx.test.core.app.ApplicationProvider
import fr.pierresdefrance.data.*
import kotlinx.coroutines.*
import okhttp3.*
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.ResponseBody.Companion.toResponseBody
import okio.Timeout
import org.junit.Assert.*
import org.junit.Test

class ImageResolverTest {
    private class PendingCall(private val original: Request): Call {
        val started=CompletableDeferred<Unit>()
        @Volatile private var cancelled=false
        private var callback: Callback?=null
        override fun request()=original
        override fun execute(): Response=error("Only asynchronous requests are supported")
        override fun enqueue(responseCallback: Callback) { callback=responseCallback; started.complete(Unit) }
        override fun cancel() { cancelled=true }
        override fun isExecuted()=callback!=null
        override fun isCanceled()=cancelled
        override fun timeout()=Timeout()
        override fun clone(): Call=PendingCall(original)
        fun respond(json: String) {
            callback!!.onResponse(this,Response.Builder().request(original).protocol(Protocol.HTTP_1_1)
                .code(200).message("OK").body(json.toResponseBody("application/json".toMediaType())).build())
        }
    }

    @Test fun cancellationStopsTheCallAndDoesNotCacheAMiss()=runBlocking {
        val context=ApplicationProvider.getApplicationContext<Context>()
        val cache=context.getSharedPreferences("commons-metadata-v1",Context.MODE_PRIVATE)
        val db=MonumentDatabase.open(context)
        val ref="PA99999991"
        cache.edit().remove(ref).commit()
        try {
            val repo=MonumentRepository(db)
            val monument=repo.detail(repo.search("PA00088801").single().id)!!
                .copy(reference=ref,imageUrl="",imageLicense="")
            val pending=CompletableDeferred<PendingCall>()
            var calls=0
            val resolver=ImageResolver(context,Call.Factory { request ->
                calls++; PendingCall(request).also { pending.complete(it) }
            })
            val loading=async { resolver.resolve(monument) }
            val call=withTimeout(5000) { pending.await().also { it.started.await() } }
            assertEquals(HERITAGE_USER_AGENT,call.request().header("User-Agent"))
            loading.cancelAndJoin()
            assertTrue("Cancelling the coroutine must abort the HTTP request",call.isCanceled())
            assertFalse("An abandoned request is not a negative cache entry",cache.contains(ref))
            // A response racing with cancellation must also be safely closed.
            call.respond("{}")
            assertFalse(cache.contains(ref))
            assertEquals(1,calls)
        } finally { db.close(); cache.edit().remove(ref).commit() }
    }

    @Test fun successfulImageAndEmptySearchAreCached()=runBlocking {
        val context=ApplicationProvider.getApplicationContext<Context>()
        val cache=context.getSharedPreferences("commons-metadata-v1",Context.MODE_PRIVATE)
        val db=MonumentDatabase.open(context)
        val refs=listOf("PA99999992","PA99999993")
        for(ref in refs) cache.edit().remove(ref).commit()
        try {
            val repo=MonumentRepository(db)
            val base=repo.detail(repo.search("PA00088801").single().id)!!.copy(imageUrl="",imageLicense="")
            for((index,ref) in refs.withIndex()) {
                val pending=CompletableDeferred<PendingCall>()
                var requests=0
                val resolver=ImageResolver(context,Call.Factory { request ->
                    requests++; PendingCall(request).also { pending.complete(it) }
                })
                val monument=base.copy(reference=ref)
                val loading=async { resolver.resolve(monument) }
                val call=withTimeout(5000) { pending.await().also { it.started.await() } }
                call.respond(if(index==1) "{}" else """{"query":{"pages":{"1":{
                    "revisions":[{"slots":{"main":{"*":"{{Mérimée|$ref}}"}}}],
                    "imageinfo":[{"mime":"image/jpeg","thumburl":"https://example.org/thumb.jpg",
                    "descriptionurl":"https://commons.wikimedia.org/wiki/File:Example.jpg",
                    "extmetadata":{"LicenseShortName":{"value":"CC BY-SA 4.0"},
                    "Artist":{"value":"<b>Photographer</b>"},"LicenseUrl":{"value":"https://creativecommons.org/licenses/by-sa/4.0/"}}}]
                }}}}""")
                val image=withTimeout(5000) { loading.await() }
                if(index==0) { assertEquals("Photographer",image!!.author); assertEquals("CC BY-SA 4.0",image.license) }
                else assertNull(image)
                assertEquals(image,resolver.resolve(monument))
                assertEquals("The second visit should use the metadata cache",1,requests)
            }
        } finally { db.close(); for(ref in refs) cache.edit().remove(ref).commit() }
    }
}
