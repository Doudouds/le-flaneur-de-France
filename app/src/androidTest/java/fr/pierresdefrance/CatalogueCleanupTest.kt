package fr.pierresdefrance

import android.content.Context
import androidx.test.core.app.ApplicationProvider
import fr.pierresdefrance.data.MonumentDatabase
import org.junit.Assert.*
import org.junit.Test

class CatalogueCleanupTest {
    @Test fun obsoleteCataloguesAreRemovedOnlyAfterTheReplacementOpens() {
        val context=ApplicationProvider.getApplicationContext<Context>()
        val old="monuments-0000000000000000.db"
        val unrelated="catalogue-cleanup-test-personal.db"
        val unexpected="monuments-not-a-revision.db"
        for(name in listOf(old,unrelated,unexpected)) {
            context.openOrCreateDatabase(name,Context.MODE_PRIVATE,null).use { db ->
                db.execSQL("CREATE TABLE IF NOT EXISTS sentinel (value TEXT)")
                db.execSQL("INSERT INTO sentinel VALUES ('keep')")
            }
        }
        val db=MonumentDatabase.open(context)
        try {
            assertTrue("Building Room must not remove the old catalogue",context.getDatabasePath(old).exists())
            db.openHelper.readableDatabase.query("SELECT count(*) FROM monuments").use {
                assertTrue(it.moveToFirst()); assertEquals(46760,it.getInt(0))
            }
            assertFalse(context.getDatabasePath(old).exists())
            for(name in listOf(unrelated,unexpected)) {
                assertTrue(context.getDatabasePath(name).exists())
                context.openOrCreateDatabase(name,Context.MODE_PRIVATE,null).use { other ->
                    other.rawQuery("SELECT value FROM sentinel",null).use { cursor ->
                        assertTrue(cursor.moveToFirst()); assertEquals("keep",cursor.getString(0))
                    }
                }
            }
        } finally {
            db.close()
            for(name in listOf(old,unrelated,unexpected)) context.deleteDatabase(name)
        }
    }
}
