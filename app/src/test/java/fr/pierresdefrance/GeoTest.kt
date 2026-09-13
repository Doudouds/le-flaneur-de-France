package fr.pierresdefrance
import fr.pierresdefrance.domain.*
import org.junit.Assert.*
import org.junit.Test

class GeoTest {
    @Test fun distance() {
        assertEquals(391.5,Geo.distance(Position(48.8566,2.3522),Position(45.764,4.8357)),1.0)
        assertEquals(22.24,Geo.distance(Position(0.0,179.9),Position(0.0,-179.9)),.1)
        assertEquals(0.0,Geo.distance(Position(0.0,0.0),Position(0.0,0.0)),0.0)
    }
    @Test fun adaptiveRadius() {
        assertEquals(5.0,Geo.chooseRadius { if(it>=5) 18 else 4 },0.0)
        assertEquals(1.0,Geo.chooseRadius { 400 },0.0)
        assertEquals(50.0,Geo.chooseRadius { 0 },0.0)
        assertTrue(Geo.reuseNearby(Position(48.0,2.0),Position(48.001,2.0),1000))
        assertFalse(Geo.reuseNearby(Position(48.0,2.0),Position(48.0,2.0),130000))
    }
    @Test fun textSearch() {
        assertEquals("chateau coeur",Search.normalize("CHÂTEAU, cœur"))
        assertEquals("mont* saint* mich*",Search.match("Mont-Saint-Mich"))
        assertEquals("",Search.match("*\""))
    }
    @Test fun bounds() {
        val b=Geo.bounds(Position(0.0,179.9),50.0)
        assertEquals(2,b.parts().size)
        assertTrue(Bounds(40.0,-5.0,52.0,10.0).contains(Bounds(48.0,2.0,49.0,3.0)))
        assertEquals(4 to 4,Geo.tile(Position(0.0,0.0),3))
    }
}
