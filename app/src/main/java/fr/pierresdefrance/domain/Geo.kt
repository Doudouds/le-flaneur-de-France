package fr.pierresdefrance.domain

import java.text.Normalizer
import java.util.Locale
import kotlin.math.*

data class Position(val latitude: Double, val longitude: Double)
data class Bounds(val south: Double, val west: Double, val north: Double, val east: Double) {
    fun contains(other: Bounds) = west <= east && other.west <= other.east &&
        south <= other.south && north >= other.north && west <= other.west && east >= other.east
    fun padded(): Bounds {
        if (west > east) return this
        val dy=(north-south)*.2; val dx=(east-west)*.2
        return Bounds(max(-85.0,south-dy),max(-180.0,west-dx),min(85.0,north+dy),min(180.0,east+dx))
    }
    fun parts(): List<Bounds> = if(west<=east) listOf(this) else
        listOf(copy(east=180.0),copy(west=-180.0))
}
object Geo {
    val radii = listOf(1.0,2.0,5.0,10.0,20.0,50.0)
    fun distance(a: Position,b: Position): Double {
        val p=Math.toRadians(a.latitude); val q=Math.toRadians(b.latitude)
        val h=sin((q-p)/2).pow(2)+cos(p)*cos(q)*sin(Math.toRadians(b.longitude-a.longitude)/2).pow(2)
        return 6371.0088*2*asin(sqrt(h.coerceIn(0.0,1.0)))
    }
    fun bounds(p: Position,km: Double): Bounds {
        val angular=km/6371.0088; val dy=Math.toDegrees(angular)
        val south=max(-90.0,p.latitude-dy); val north=min(90.0,p.latitude+dy)
        if(south<=-90 || north>=90) return Bounds(south,-180.0,north,180.0)
        val dx=Math.toDegrees(asin((sin(angular)/cos(Math.toRadians(p.latitude))).coerceIn(-1.0,1.0)))
        fun wrap(v: Double)=((v+540)%360)-180
        return Bounds(south,wrap(p.longitude-dx),north,wrap(p.longitude+dx))
    }
    fun tile(p: Position,z: Int): Pair<Int,Int> {
        val n=2.0.pow(z); val lat=Math.toRadians(p.latitude.coerceIn(-85.05112878,85.05112878))
        return (((p.longitude+180)/360*n).toInt().coerceIn(0,n.toInt()-1)) to
            (((1-asinh(tan(lat))/PI)/2*n).toInt().coerceIn(0,n.toInt()-1))
    }
    fun chooseRadius(count: (Double)->Int): Double = radii.firstOrNull { count(it)>=10 } ?: radii.last()
    fun reuseNearby(previous: Position,current: Position,ageMillis: Long)=ageMillis<120_000 && distance(previous,current)<.25
}
object Search {
    fun normalize(text: String): String = Normalizer.normalize(text.lowercase(Locale.ROOT).replace("œ","oe").replace("æ","ae"),Normalizer.Form.NFKD)
        .replace(Regex("\\p{M}+"),"").replace(Regex("[^a-z0-9]+")," ").trim()
    fun match(text: String)=normalize(text).split(' ').filter { it.isNotBlank() }.take(12).joinToString(" ") { "$it*" }
}
