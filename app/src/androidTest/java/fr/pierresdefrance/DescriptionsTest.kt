package fr.pierresdefrance

import androidx.test.core.app.ApplicationProvider
import fr.pierresdefrance.data.*
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test

class DescriptionsTest {
    @Test fun allNoticesHaveSourcedText() {
        val db=MonumentDatabase.open(ApplicationProvider.getApplicationContext())
        try {
            db.openHelper.readableDatabase.query("SELECT count(*) FROM monuments WHERE trim(description)='' OR trim(descriptionSource)=''").use {
                assertTrue(it.moveToFirst()); assertEquals(0,it.getInt(0))
            }
            db.openHelper.readableDatabase.query("SELECT count(*) FROM monuments WHERE descriptionSource LIKE 'Synthèse%'").use {
                assertTrue(it.moveToFirst()); assertTrue(it.getInt(0)>0)
            }
        } finally { db.close() }
    }
    @Test fun wikipediaParserAcceptsArticleButRejectsMissingAndDisambiguation() {
        fun result(page: String)=WikipediaDescriptions.parse(JSONObject("""{"query":{"pages":[$page]}}"""))
        val article="""{"ns":0,"title":"Désert de Retz","extract":"Un jardin à Chambourcy.","fullurl":"https://fr.wikipedia.org/wiki/Désert_de_Retz","lastrevid":123} """
        val description=result(article)!!
        assertEquals("Un jardin à Chambourcy.",description.text)
        assertTrue(description.source.contains("CC BY-SA 4.0"))
        assertEquals(123L,description.revision)
        assertNull(result("""{"ns":0,"missing":true}"""))
        assertNull(result(article.trim().dropLast(1)+""","pageprops":{"disambiguation":""}}"""))
    }
}
