package fr.pierresdefrance

import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import fr.pierresdefrance.data.*
import fr.pierresdefrance.domain.*
import kotlinx.coroutines.runBlocking
import org.junit.*
import org.junit.runner.RunWith
import android.util.Log
import kotlin.system.measureTimeMillis

@RunWith(AndroidJUnit4::class)
class CatalogueTest {
    private lateinit var db: MonumentDatabase
    @Before fun setup() { db=MonumentDatabase.open(ApplicationProvider.getApplicationContext()) }
    @After fun close() { db.close() }
    @Test fun fullDatasetAndQueries()=runBlocking {
        val repo=MonumentRepository(db)
        Assert.assertEquals(46760,repo.total()) // pins the supplied snapshot intentionally
        val eiffelRow=repo.search("PA00088801").single()
        val eiffel=repo.detail(eiffelRow.id)!!
        Assert.assertEquals(3,eiffel.visualLevel)
        Assert.assertEquals(3,eiffelRow.level)
        Assert.assertTrue(eiffel.globalScore>=80)
        Assert.assertTrue(eiffel.notoriety>0)
        Assert.assertTrue(eiffel.scoreEvidence.contains("national-v2"))
        val eiffelBounds=Bounds(eiffel.latitude!!-.003,eiffel.longitude!!-.003,eiffel.latitude+.003,eiffel.longitude+.003)
        Assert.assertEquals(3,repo.map(eiffelBounds,16.0).items.single { it.id==eiffel.id }.visualLevel)
        for(ref in listOf("PA00113040","PA00087398")) {
            val row=repo.search(ref).single()
            val detail=repo.detail(row.id)!!
            Assert.assertTrue(detail.wikipediaUrl.contains("fr.wikipedia.org/wiki/"))
            Assert.assertTrue(detail.description.isNotBlank())
            Assert.assertTrue(detail.descriptionSource.startsWith("Wikipédia"))
        }
        val searchMs=measureTimeMillis {
            val found=repo.search("CHÂMBORD")
            Assert.assertTrue(found.any { it.name.contains("Chambord",true) || it.commune.contains("Chambord",true) })
            Assert.assertTrue(repo.search("Mont Saint Mich").isNotEmpty())
            Assert.assertTrue(repo.search("Chartres").isNotEmpty())
            Assert.assertTrue(repo.search("PA2A000001").isNotEmpty())
        }
        val viewportMs=measureTimeMillis {
            for(b in listOf(Bounds(41.0,-5.5,51.6,10.0),Bounds(48.81,2.22,48.92,2.43),Bounds(44.80,-.64,44.89,-.52),Bounds(45.70,4.75,45.81,4.91))) {
                val result=repo.map(b,if(b.south==41.0) 4.6 else 12.0)
                Assert.assertTrue(result.items.isNotEmpty()); Assert.assertTrue(result.items.size<=6000)
            }
        }
        val nearbyMs=measureTimeMillis {
            for(p in listOf(Position(48.8566,2.3522),Position(44.1,3.4))) {
                val near=repo.nearby(p,true)
                Assert.assertTrue(near.radius in Geo.radii)
                Assert.assertTrue(near.rows.zipWithNext().all { (a,b)->a.distance!!<=b.distance!! })
                Assert.assertTrue(near.rows.all { it.distance!!<=near.radius })
            }
        }
        Log.i("CatalogueBenchmark","search4=${searchMs}ms viewport4=${viewportMs}ms nearby2=${nearbyMs}ms")
        Unit
    }
}
