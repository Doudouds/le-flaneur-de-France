package fr.pierresdefrance.ui

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import fr.pierresdefrance.data.*
import fr.pierresdefrance.domain.*
import fr.pierresdefrance.location.LocationProvider
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*

data class DiscoveryState(
    val loading: Boolean=true,val total: Int=0,val map: MapResult?=null,
    val position: Position?=null,val focus: Position?=null,val focusSerial: Int=0,
    val focusZoom: Double=15.5,val exploration: AddressPlace?=null,val nearbyLoading: Boolean=false,
    val addressQuery: String="",val addressResults: List<AddressPlace> = emptyList(),
    val addressSearching: Boolean=false,val addressMessage: String?=null,
    val nearby: Nearby?=null,val query: String="",val rows: List<MonumentRow> = emptyList(),
    val searching: Boolean=false,val hasMore: Boolean=false,
    val detail: MonumentDetail?=null,val selectedId: Long?=null,val detailLoading: Boolean=false,
    val image: HeritageImage?=null,val locating: Boolean=false,val message: String?=null,
    val fatal: Boolean=false,
    val mapChoices: List<MapChoice> = emptyList(),
)
class DiscoveryViewModel @JvmOverloads constructor(application: Application,private val addresses: AddressSearch=IgnAddressSearch()): AndroidViewModel(application) {
    private val db=MonumentDatabase.open(application)
    private val repository=MonumentRepository(db)
    private val images=ImageResolver(application)
    private val wikipedia=WikipediaDescriptions(application)
    private val location=LocationProvider(application)
    private val mutable=MutableStateFlow(DiscoveryState())
    val state=mutable.asStateFlow()
    private var mapJob: Job?=null; private var searchJob: Job?=null; private var detailJob: Job?=null
    private var locationJob: Job?=null
    private var mapSelectionJob: Job?=null
    private var addressJob: Job?=null; private var nearbyJob: Job?=null
    private var offset=0
    init { viewModelScope.launch {
        try {
            val total=repository.total(); val rows=repository.search("")
            mutable.update { it.copy(loading=false,total=total,rows=it.nearby?.rows ?: rows,
                hasMore=it.nearby==null && rows.size==50) }
        } catch(e: Exception) { mutable.update { it.copy(loading=false,fatal=true,message="Le catalogue local n’a pas pu être ouvert. Réessayez après avoir relancé l’application.") } }
    } }
    fun viewport(bounds: Bounds,zoom: Double) {
        mapJob?.cancel(); mapJob=viewModelScope.launch {
            delay(220)
            try { val result=repository.map(bounds,zoom); ensureActive(); mutable.update { it.copy(map=result) } }
            catch(e: CancellationException) { throw e }
            catch(e: Exception) { message("La zone n’a pas pu être chargée.") }
        }
    }
    fun search(query: String) {
        searchJob?.cancel(); offset=0
        mutable.update { it.copy(query=query,rows=emptyList(),searching=true,hasMore=false) }
        if(query.isBlank() && mutable.value.nearbyLoading) return
        searchJob=viewModelScope.launch {
            delay(200)
            try {
                val nearby=mutable.value.nearby
                val rows=if(query.isBlank() && nearby!=null) nearby.rows else repository.search(query)
                ensureActive(); offset=rows.size
                mutable.update { it.copy(rows=rows,searching=false,hasMore=(query.isNotBlank() || nearby==null) && rows.size==50) }
            } catch(e: CancellationException) { throw e }
            catch(e: Exception) { mutable.update { it.copy(searching=false,message="La recherche n’a pas abouti.") } }
        }
    }
    fun more() {
        if(mutable.value.searching || !mutable.value.hasMore) return
        val query=mutable.value.query; val next=mutable.value.rows.size
        mutable.update { it.copy(searching=true) }
        searchJob=viewModelScope.launch {
            try {
                val rows=repository.search(query,next); ensureActive(); offset=next+rows.size
                mutable.update { it.copy(rows=it.rows+rows,searching=false,hasMore=rows.size==50) }
            } catch(e: CancellationException) { throw e }
            catch(e: Exception) { mutable.update { it.copy(searching=false,message="Chargement interrompu. Réessayez.") } }
        }
    }
    fun selectOnMap(id: Long) {
        dismiss()
        mapSelectionJob=viewModelScope.launch {
            try {
                val choices=repository.mapChoices(id); ensureActive()
                mapSelectionJob=null
                if(choices.size==1) select(choices.single().id)
                else mutable.update { it.copy(mapChoices=choices) }
            } catch(e: CancellationException) { throw e }
            catch(e: Exception) { message("Les monuments à cet endroit n’ont pas pu être chargés.") }
        }
    }
    fun select(id: Long) {
        mapSelectionJob?.cancel()
        detailJob?.cancel(); mutable.update { it.copy(mapChoices=emptyList(),selectedId=id,detail=null,image=null,detailLoading=true) }
        detailJob=viewModelScope.launch {
            try {
                val detail=repository.detail(id); ensureActive()
                mutable.update { it.copy(detail=detail,detailLoading=false) }
                if(detail!=null) {
                    coroutineScope {
                        launch {
                            val image=images.resolve(detail); ensureActive(); mutable.update { it.copy(image=image) }
                        }
                        launch {
                            if(detail.wikipediaUrl.isNotBlank() && (detail.descriptionSource.startsWith("Synthèse") || detail.description==detail.history)) {
                                val description=wikipedia.resolve(detail); ensureActive()
                                if(description!=null) mutable.update { it.copy(detail=detail.copy(description=description.text,
                                    descriptionSource=description.source,wikipediaUrl=description.url)) }
                            }
                        }
                    }
                }
            } catch(e: CancellationException) { throw e }
            catch(e: Exception) { mutable.update { it.copy(detailLoading=false,message="Cette fiche est indisponible.") } }
        }
    }
    fun dismiss() { mapSelectionJob?.cancel(); detailJob?.cancel(); mutable.update { it.copy(mapChoices=emptyList(),detail=null,selectedId=null,image=null,detailLoading=false) } }
    fun focus(position: Position,zoom: Double=15.5) { mutable.update { it.copy(focus=position,focusZoom=zoom,focusSerial=it.focusSerial+1) } }
    fun editAddress(query: String) {
        addressJob?.cancel()
        mutable.update { it.copy(addressQuery=query.take(200),addressResults=emptyList(),addressSearching=false,addressMessage=null) }
        if(query.trim().length>=3) scheduleAddressSearch(350)
    }
    fun searchAddress() {
        if(mutable.value.addressSearching) return
        scheduleAddressSearch(0)
    }
    private fun scheduleAddressSearch(debounceMillis: Long) {
        val query=mutable.value.addressQuery.trim()
        if(query.length<3) {
            mutable.update { it.copy(addressMessage="Saisissez au moins 3 caractères (ajoutez le département pour un nom court).") }; return
        }
        addressJob?.cancel()
        addressJob=viewModelScope.launch {
            delay(debounceMillis)
            mutable.update { it.copy(addressSearching=true,addressResults=emptyList(),addressMessage=null) }
            try {
                val found=addresses.search(query); ensureActive()
                mutable.update { it.copy(addressSearching=false,addressResults=found,
                    addressMessage=if(found.isEmpty()) "Aucune adresse trouvée. Précisez la ville ou le code postal." else null) }
            } catch(e: CancellationException) { throw e }
            catch(e: Exception) { mutable.update { it.copy(addressSearching=false,addressMessage="Recherche d’adresse indisponible. Vérifiez votre connexion puis réessayez.") } }
        }
    }
    fun usePlace(place: AddressPlace) {
        locationJob?.cancel(); addressJob?.cancel()
        mutable.update { it.copy(locating=false,addressSearching=false,addressResults=emptyList(),addressMessage=null,addressQuery=place.label) }
        focus(place.position,place.zoom)
        loadNearby(place.position,place,resetQuery=true)
    }
    private fun loadNearby(origin: Position,place: AddressPlace?,resetQuery: Boolean) {
        nearbyJob?.cancel()
        if(resetQuery || mutable.value.query.isBlank()) searchJob?.cancel()
        mutable.update {
            val showNearby=resetQuery || it.query.isBlank()
            it.copy(exploration=place,nearby=null,nearbyLoading=true,query=if(resetQuery) "" else it.query,
                rows=if(showNearby) emptyList() else it.rows,searching=if(showNearby) true else it.searching,
                hasMore=if(showNearby) false else it.hasMore)
        }
        nearbyJob=viewModelScope.launch {
            try {
                val nearby=repository.nearby(origin,force=resetQuery); ensureActive()
                mutable.update { it.copy(nearby=nearby,nearbyLoading=false,
                    rows=if(it.query.isBlank()) nearby.rows else it.rows,
                    searching=if(it.query.isBlank()) false else it.searching,
                    hasMore=if(it.query.isBlank()) false else it.hasMore) }
            } catch(e: CancellationException) { throw e }
            catch(e: Exception) { mutable.update { it.copy(nearbyLoading=false,searching=false,message="Les monuments autour de ce lieu n’ont pas pu être chargés. Réessayez.") } }
        }
    }
    fun locate(center: Boolean=true) {
        // Foreground refresh must never replace a place explicitly chosen on the map.
        if(!center && mutable.value.exploration!=null) return
        locationJob?.cancel(); locationJob=viewModelScope.launch {
            mutable.update { it.copy(locating=true) }
            try {
                val position=location.current(highAccuracy=center)
                ensureActive()
                if(position==null) message("Position indisponible. La carte et la recherche restent accessibles.")
                else {
                    mutable.update { it.copy(position=position) }
                    if(center) { editAddress(""); focus(position) }
                    if(center || mutable.value.exploration==null) loadNearby(position,null,resetQuery=center)
                }
            } catch(e: CancellationException) { throw e }
            catch(e: Exception) { message("La localisation n’a pas abouti. La recherche nationale reste disponible.") }
            finally { mutable.update { it.copy(locating=false) } }
        }
    }
    fun stopLocation() { locationJob?.cancel() }
    fun message(text: String?) { mutable.update { it.copy(message=text) } }
    override fun onCleared() { db.close() }
}
