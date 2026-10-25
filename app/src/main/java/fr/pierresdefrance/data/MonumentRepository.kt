package fr.pierresdefrance.data

import androidx.sqlite.db.SimpleSQLiteQuery
import fr.pierresdefrance.domain.*
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import android.os.SystemClock
import kotlin.math.*

data class MonumentMapItem(val id: Long,val latitude: Double,val longitude: Double,val importance: Int,val count: Int=1,val visualLevel: Int=1)
data class MonumentRow(val id: Long,val name: String,val commune: String,val department: String,val level: Int,val distance: Double?=null)
data class Nearby(val origin: Position,val radius: Double,val count: Int,val rows: List<MonumentRow>,val computedAt: Long=SystemClock.elapsedRealtime())
data class MapResult(val bounds: Bounds,val level: Int,val aggregated: Boolean,val items: List<MonumentMapItem>)
data class MapChoice(val id: Long,val name: String,val commune: String,val address: String,val reference: String)

class MonumentRepository(val database: MonumentDatabase) {
    private var mapCache: MapResult?=null
    private var nearbyCache: Nearby?=null
    suspend fun detail(id: Long)=database.monuments().detail(id)
    suspend fun mapChoices(id: Long): List<MapChoice> = withContext(Dispatchers.IO) {
        // Use the stored coordinates: the renderer can round GeoJSON doubles.
        database.query("SELECT m.id,m.name,m.commune,m.address,m.reference FROM monuments anchor JOIN monuments m ON m.latitude=anchor.latitude AND m.longitude=anchor.longitude WHERE anchor.id=? ORDER BY m.searchName,m.id",
            arrayOf(id)).use { c -> buildList {
                while(c.moveToNext()) add(MapChoice(c.getLong(0),c.getString(1),c.getString(2),c.getString(3),c.getString(4)))
            } }
    }
    suspend fun total(): Int=withContext(Dispatchers.IO) {
        database.query("SELECT count(*) FROM monuments",emptyArray()).use { it.moveToFirst(); it.getInt(0) }
    }
    private fun boxWhere(bounds: Bounds): Pair<String,Array<Any>> {
        val args=mutableListOf<Any>()
        val sql=bounds.parts().joinToString(" OR ") {
            args.addAll(listOf(it.south,it.north,it.west,it.east))
            "(latitude BETWEEN ? AND ? AND longitude BETWEEN ? AND ?)"
        }
        return "($sql)" to args.toTypedArray()
    }
    suspend fun map(bounds: Bounds,zoom: Double): MapResult=withContext(Dispatchers.IO) {
        val level=(floor(zoom).toInt()+3).coerceIn(3,18)
        mapCache?.takeIf { it.level==level && it.bounds.contains(bounds) }?.let { return@withContext it }
        val padded=bounds.padded(); val (where,args)=boxWhere(padded)
        var points=emptyList<MonumentMapItem>()
        if(zoom>=11) {
            points=database.query("SELECT id,latitude,longitude,globalScore,visualLevel FROM monuments WHERE $where LIMIT 6001",args).use { c ->
                buildList { while(c.moveToNext()) add(MonumentMapItem(c.getLong(0),c.getDouble(1),c.getDouble(2),c.getInt(3),visualLevel=c.getInt(4))) }
            }
        }
        val aggregate=zoom<11 || points.size>6000
        if(aggregate) {
            points=padded.parts().flatMap { b ->
                val (x0,y1)=Geo.tile(Position(b.south,b.west),level)
                val (x1,y0)=Geo.tile(Position(b.north,b.east),level)
                database.query("SELECT c.majorId,c.latitude,c.longitude,c.importance,c.count,m.visualLevel FROM map_cells c JOIN monuments m ON m.id=c.majorId WHERE c.level=? AND c.x BETWEEN ? AND ? AND c.y BETWEEN ? AND ?",
                    arrayOf(level,x0,x1,y0,y1)).use { c ->
                    buildList { while(c.moveToNext()) add(MonumentMapItem(c.getLong(0),c.getDouble(1),c.getDouble(2),c.getInt(3),c.getInt(4),c.getInt(5))) }
                }
            }.distinct()
        }
        MapResult(padded,level,aggregate,points).also { mapCache=it }
    }
    suspend fun search(text: String,offset: Int=0): List<MonumentRow> = withContext(Dispatchers.IO) {
        val match=Search.match(text); val normalized=Search.normalize(text)
        val projection="m.id,m.name,m.commune,m.department,m.visualLevel"
        val (sql,args)=if(match.isBlank()) {
            "SELECT $projection FROM monument_list m ORDER BY m.searchName,m.id LIMIT 50 OFFSET ?" to arrayOf<Any>(offset)
        } else {
            // FTS restricts candidates before this small relevance sort; no full-table wildcard scan.
            "SELECT $projection FROM monument_fts f JOIN monument_list m ON m.id=f.docid WHERE monument_fts MATCH ? ORDER BY CASE WHEN m.searchName=? THEN 0 WHEN m.searchName GLOB ? THEN 1 ELSE 2 END,m.globalScore DESC,m.searchName,m.id LIMIT 50 OFFSET ?" to
                arrayOf<Any>(match,normalized,"$normalized*",offset)
        }
        database.query(sql,args).use { c -> buildList {
            while(c.moveToNext()) add(MonumentRow(c.getLong(0),c.getString(1),c.getString(2),c.getString(3),c.getInt(4)))
        } }
    }
    private fun candidates(origin: Position,radius: Double): List<Pair<Long,Double>> {
        val (where,args)=boxWhere(Geo.bounds(origin,radius))
        return database.query("SELECT id,latitude,longitude FROM monuments WHERE $where",args).use { c -> buildList {
            while(c.moveToNext()) {
                val d=Geo.distance(origin,Position(c.getDouble(1),c.getDouble(2)))
                if(d<=radius) add(c.getLong(0) to d)
            }
        } }
    }
    suspend fun nearby(origin: Position,force: Boolean=false): Nearby=withContext(Dispatchers.IO) {
        nearbyCache?.takeIf { !force && Geo.reuseNearby(it.origin,origin,SystemClock.elapsedRealtime()-it.computedAt) }?.let { return@withContext it }
        var selected=emptyList<Pair<Long,Double>>()
        val radius=Geo.chooseRadius { r -> candidates(origin,r).also { selected=it }.size }
        val sorted=selected.sortedWith(compareBy<Pair<Long,Double>> { it.second }.thenBy { it.first }).take(200)
        val byId=if(sorted.isEmpty()) emptyMap() else database.query(
            "SELECT id,name,commune,department,visualLevel FROM monument_list WHERE id IN (${sorted.joinToString(",") { "?" }})",
            sorted.map { it.first }.toTypedArray()).use { c -> buildMap {
                while(c.moveToNext()) put(c.getLong(0),MonumentRow(c.getLong(0),c.getString(1),c.getString(2),c.getString(3),c.getInt(4)))
            } }
        Nearby(origin,radius,selected.size,sorted.mapNotNull { (id,d) -> byId[id]?.copy(distance=d) }).also { nearbyCache=it }
    }
}
