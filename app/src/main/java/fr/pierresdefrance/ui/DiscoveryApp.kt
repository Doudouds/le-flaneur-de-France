package fr.pierresdefrance.ui

import android.Manifest
import android.content.ActivityNotFoundException
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.widget.Toast
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.List
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import coil3.compose.SubcomposeAsyncImage
import coil3.request.ImageRequest
import coil3.network.NetworkHeaders
import coil3.network.httpHeaders
import fr.pierresdefrance.R
import fr.pierresdefrance.data.*
import org.json.JSONObject
import fr.pierresdefrance.domain.Position
import java.util.Locale

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DiscoveryApp(vm: DiscoveryViewModel) {
    val state by vm.state.collectAsStateWithLifecycle()
    var tab by rememberSaveable { mutableIntStateOf(0) }
    val context=LocalContext.current
    val lifecycle=LocalLifecycleOwner.current.lifecycle
    fun permitted()=listOf(Manifest.permission.ACCESS_COARSE_LOCATION,Manifest.permission.ACCESS_FINE_LOCATION).any {
        ContextCompat.checkSelfPermission(context,it)==PackageManager.PERMISSION_GRANTED
    }
    val permission=rememberLauncherForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) {
        if(permitted()) vm.locate() else vm.message("Localisation refusée. Vous pouvez explorer toute la France et rechercher un monument.")
    }
    fun locate() {
        if(permitted()) vm.locate() else permission.launch(arrayOf(Manifest.permission.ACCESS_COARSE_LOCATION,Manifest.permission.ACCESS_FINE_LOCATION))
    }
    DisposableEffect(lifecycle) {
        val observer=LifecycleEventObserver { _,event ->
            if(event==Lifecycle.Event.ON_START && permitted()) vm.locate(center=false)
            if(event==Lifecycle.Event.ON_STOP) vm.stopLocation()
        }
        lifecycle.addObserver(observer)
        if(lifecycle.currentState.isAtLeast(Lifecycle.State.STARTED) && permitted()) vm.locate(center=false)
        onDispose { lifecycle.removeObserver(observer); vm.stopLocation() }
    }
    val snackbar=remember { SnackbarHostState() }
    LaunchedEffect(state.message) { state.message?.let { snackbar.showSnackbar(it); vm.message(null) } }
    BackHandler(enabled=tab!=0 || state.selectedId!=null) { if(state.selectedId!=null) vm.dismiss() else tab=0 }
    Scaffold(snackbarHost={ SnackbarHost(snackbar) },bottomBar={
        NavigationBar(containerColor=MaterialTheme.colorScheme.surface) {
            NavigationBarItem(selected=tab==0,onClick={tab=0},icon={Icon(HeritageIcons.Map,null)},label={Text("Carte")})
            NavigationBarItem(selected=tab==1,onClick={tab=1},icon={Icon(Icons.AutoMirrored.Filled.List,null)},label={Text("Liste")})
            NavigationBarItem(selected=tab==2,onClick={tab=2},icon={Icon(Icons.Default.Info,null)},label={Text("Aide")})
        }
    }) { padding ->
        Box(Modifier.fillMaxSize().padding(padding)) {
            if(state.loading) {
                Column(Modifier.align(Alignment.Center),horizontalAlignment=Alignment.CenterHorizontally,verticalArrangement=Arrangement.spacedBy(16.dp)) {
                    Icon(HeritageIcons.Monument,null,Modifier.size(44.dp),tint=MaterialTheme.colorScheme.primary)
                    Text(stringResource(R.string.app_name),style=MaterialTheme.typography.headlineMedium)
                    CircularProgressIndicator(); Text("Préparation du catalogue local…")
                }
            } else if(state.fatal) {
                Text(state.message ?: "Catalogue indisponible",Modifier.align(Alignment.Center).padding(32.dp))
            } else {
                MapScreen(state,vm,tab==0)
                if(tab==0) {
                    Surface(Modifier.align(Alignment.TopCenter).padding(12.dp).fillMaxWidth(),shape=RoundedCornerShape(18.dp),shadowElevation=3.dp) {
                        Column(Modifier.padding(horizontal=12.dp,vertical=6.dp)) {
                            AddressSearchBox(state,vm)
                        }
                    }
                    Column(Modifier.align(Alignment.BottomEnd).padding(end=16.dp,bottom=44.dp),horizontalAlignment=Alignment.End,verticalArrangement=Arrangement.spacedBy(12.dp)) {
                        state.nearby?.let { n ->
                            FilledTonalButton(onClick={vm.search("");tab=1}) { Text("${n.count} monuments à moins de ${n.radius.toInt()} km") }
                        }
                        FloatingActionButton(onClick={locate()},containerColor=MaterialTheme.colorScheme.surface) {
                            if(state.locating) CircularProgressIndicator(Modifier.size(24.dp),strokeWidth=2.dp)
                            else Icon(HeritageIcons.Locate,"Recentrer sur ma position")
                        }
                    }
                } else if(tab==1) MonumentList(state,vm) else HelpScreen()
            }
        }
    }
    if(state.selectedId!=null) {
        ModalBottomSheet(onDismissRequest=vm::dismiss,sheetState=rememberModalBottomSheetState(skipPartiallyExpanded=true)) {
            if(state.detailLoading) Box(Modifier.fillMaxWidth().height(180.dp),contentAlignment=Alignment.Center) { CircularProgressIndicator() }
            else state.detail?.let { m ->
                MonumentSheet(m,state.image) {
                    if(m.latitude!=null && m.longitude!=null) { vm.focus(Position(m.latitude,m.longitude)); tab=0; vm.dismiss() }
                }
            } ?: Text("Cette notice est indisponible.",Modifier.padding(24.dp))
        }
    }
}

@Composable
private fun MonumentList(state: DiscoveryState,vm: DiscoveryViewModel) {
    Surface(Modifier.fillMaxSize()) {
        Column(Modifier.fillMaxSize()) {
            Column(Modifier.padding(horizontal=20.dp,vertical=18.dp),verticalArrangement=Arrangement.spacedBy(12.dp)) {
                Text("À découvrir",style=MaterialTheme.typography.headlineLarge)
                OutlinedTextField(value=state.query,onValueChange=vm::search,modifier=Modifier.fillMaxWidth(),singleLine=true,
                    placeholder={Text("Rechercher un monument")},leadingIcon={Icon(Icons.Default.Search,null)},
                    trailingIcon={if(state.query.isNotEmpty()) IconButton(onClick={vm.search("")}) {Icon(Icons.Default.Close,"Effacer la recherche")}},
                    shape=RoundedCornerShape(16.dp))
                Text(when { state.query.isNotBlank()->"Recherche dans toute la France"
                    state.exploration!=null->"Autour de ${state.exploration.label}" +
                        (state.nearby?.let { " · moins de ${it.radius.toInt()} km · par distance" } ?: " · chargement…")
                    state.nearby!=null->"Autour de vous · moins de ${state.nearby.radius.toInt()} km · par distance"
                    else->"Toute la France · par nom · localisation facultative" },style=MaterialTheme.typography.bodySmall,color=MaterialTheme.colorScheme.onSurfaceVariant)
            }
            if(state.searching) LinearProgressIndicator(Modifier.fillMaxWidth())
            LazyColumn(Modifier.fillMaxSize(),contentPadding=PaddingValues(bottom=24.dp)) {
                if(state.rows.isEmpty() && !state.searching) item {
                    Column(Modifier.fillMaxWidth().padding(32.dp),horizontalAlignment=Alignment.CenterHorizontally,verticalArrangement=Arrangement.spacedBy(12.dp)) {
                        Icon(HeritageIcons.Monument,null,Modifier.size(42.dp),tint=MaterialTheme.colorScheme.secondary)
                        Text(if(state.query.isBlank()) "Aucun monument dans ce rayon. Essayez une recherche nationale." else "Aucun résultat. Essayez un nom ou une commune.")
                    }
                }
                items(state.rows,key={it.id}) { row ->
                    Row(Modifier.fillMaxWidth().clickable {vm.select(row.id)}.padding(horizontal=20.dp,vertical=15.dp),verticalAlignment=Alignment.CenterVertically,horizontalArrangement=Arrangement.spacedBy(14.dp)) {
                        Box(Modifier.size(48.dp).clip(RoundedCornerShape(12.dp)).background(MaterialTheme.colorScheme.surfaceContainer),contentAlignment=Alignment.Center) {
                            Icon(HeritageIcons.Monument,null,tint=MaterialTheme.colorScheme.primary)
                        }
                        Column(Modifier.weight(1f),verticalArrangement=Arrangement.spacedBy(4.dp)) {
                            Text(row.name,style=MaterialTheme.typography.titleMedium)
                            Text("${communeLabel(row.commune)} · ${row.department}",style=MaterialTheme.typography.bodySmall,color=MaterialTheme.colorScheme.onSurfaceVariant)
                            Text("★".repeat(row.level),style=MaterialTheme.typography.labelSmall,color=MaterialTheme.colorScheme.secondary)
                        }
                        row.distance?.let { Text(if(it<1) "${(it*1000).toInt()} m" else String.format(Locale.FRANCE,"%.1f km",it),style=MaterialTheme.typography.labelMedium) }
                        Icon(HeritageIcons.Chevron,null,tint=MaterialTheme.colorScheme.outline)
                    }
                    HorizontalDivider(Modifier.padding(start=82.dp,end=20.dp),color=MaterialTheme.colorScheme.outlineVariant.copy(alpha=.5f))
                }
                if(state.hasMore) item {
                    TextButton(onClick=vm::more,enabled=!state.searching,modifier=Modifier.fillMaxWidth()) { Text("Afficher la suite") }
                }
                if(state.query.isBlank() && state.nearby!=null && state.nearby.count>200) item {
                    Text("Les 200 monuments les plus proches sont affichés. Recherchez un nom pour élargir votre découverte.",Modifier.padding(20.dp),style=MaterialTheme.typography.bodySmall)
                }
            }
        }
    }
}

@Composable
private fun MonumentSheet(m: MonumentDetail,image: HeritageImage?,onMap: ()->Unit) {
    val context=LocalContext.current
    Column(Modifier.fillMaxWidth().verticalScroll(rememberScrollState()).padding(horizontal=24.dp).padding(bottom=36.dp),verticalArrangement=Arrangement.spacedBy(16.dp)) {
        Box(Modifier.fillMaxWidth().height(215.dp).clip(RoundedCornerShape(20.dp)).background(MaterialTheme.colorScheme.surfaceContainer),contentAlignment=Alignment.Center) {
            @Composable fun placeholder() {
                Column(Modifier.fillMaxSize(),horizontalAlignment=Alignment.CenterHorizontally,verticalArrangement=Arrangement.spacedBy(12.dp,Alignment.CenterVertically)) {
                    Icon(HeritageIcons.Monument,null,Modifier.size(54.dp),tint=MaterialTheme.colorScheme.secondary)
                    Text("Un lieu, une histoire",style=MaterialTheme.typography.titleLarge,color=MaterialTheme.colorScheme.secondary)
                }
            }
            if(image==null) placeholder() else SubcomposeAsyncImage(
                model=ImageRequest.Builder(context).data(image.url).size(1000,600)
                    .httpHeaders(NetworkHeaders.Builder().set("User-Agent",HERITAGE_USER_AGENT).build())
                    .build(),contentDescription="Photographie de ${m.name}",
                modifier=Modifier.fillMaxSize(),contentScale=ContentScale.Crop,loading={placeholder()},error={placeholder()})
        }
        Column(verticalArrangement=Arrangement.spacedBy(6.dp)) {
            Text(m.name,style=MaterialTheme.typography.headlineMedium)
            Text("${communeLabel(m.commune)} · ${m.departmentName}",color=MaterialTheme.colorScheme.onSurfaceVariant)
            Text("★".repeat(m.visualLevel)+"☆".repeat(3-m.visualLevel),color=MaterialTheme.colorScheme.secondary)
        }
        Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.spacedBy(8.dp)) {
            Score("Protection",m.importance,Modifier.weight(1f))
            Score("Rayonnement",m.notoriety,Modifier.weight(1f))
            Score("Indice",m.globalScore,Modifier.weight(1f))
        }
        if(m.notoriety < 0)
            Text("Note provisoire : rayonnement non mesuré. Une étoile ne signifie pas un faible intérêt.",style=MaterialTheme.typography.bodySmall,color=MaterialTheme.colorScheme.onSurfaceVariant)
        Text("Protection patrimoniale et rayonnement encyclopédique. Deux étoiles à partir de 55, trois à partir de 75. Ce repère ne mesure ni la qualité de visite ni l’accessibilité.",style=MaterialTheme.typography.bodySmall,color=MaterialTheme.colorScheme.onSurfaceVariant)
        Button(onClick={
            val uri="geo:0,0?q=${m.latitude},${m.longitude}(${Uri.encode(m.name)})"
            open(context,uri,true)
        },enabled=m.latitude!=null && m.longitude!=null,modifier=Modifier.fillMaxWidth().height(52.dp)) {
            Icon(HeritageIcons.Directions,null); Spacer(Modifier.width(8.dp));Text("Itinéraire")
        }
        if(m.latitude==null) Text("La position de ce monument n’est pas renseignée ou reste à vérifier.",style=MaterialTheme.typography.bodySmall)
        if(m.description.isNotBlank()) {
            Text("Le lieu",style=MaterialTheme.typography.titleLarge); Text(m.description)
            Text("Source : ${m.descriptionSource}",style=MaterialTheme.typography.bodySmall,color=MaterialTheme.colorScheme.onSurfaceVariant)
        }
        if(m.history.isNotBlank() && m.history!=m.description) {
            Text("Au fil du temps",style=MaterialTheme.typography.titleLarge); Text(m.history)
            Text("Source : ${m.historySource}",style=MaterialTheme.typography.bodySmall,color=MaterialTheme.colorScheme.onSurfaceVariant)
        }
        HorizontalDivider()
        Text("Un patrimoine protégé",style=MaterialTheme.typography.titleLarge)
        if(m.commune.contains(';')) Text("Communes : ${m.commune.replace(";",", ")}",style=MaterialTheme.typography.bodyMedium)
        for(text in listOf(m.protection,m.protectionDates,m.period,m.address).filter { it.isNotBlank() }) Text(text)
        if(m.protectionDetails.isNotBlank()) Text(m.protectionDetails,style=MaterialTheme.typography.bodyMedium)
        TextButton(onClick={open(context,m.popUrl)}) { Text("Voir la fiche officielle POP ↗") }
        if(m.wikipediaUrl.isNotBlank()) TextButton(onClick={open(context,m.wikipediaUrl)}) { Text("Lire sur Wikipédia ↗") }
        val ratingSource=remember(m.scoreEvidence) {
            runCatching { JSONObject(m.scoreEvidence).optString("wikidata") }.getOrDefault("")
                .takeIf { it.startsWith("https://www.wikidata.org/wiki/Q") }
        }
        if(ratingSource!=null) TextButton(onClick={open(context,ratingSource)}) { Text("Source du rayonnement ↗") }
        if(m.descriptionSource.startsWith("Wikipédia")) {
            TextButton(onClick={open(context,m.wikipediaUrl.substringBefore('#').substringBefore('?')+"?action=history")}) { Text("Contributeurs et historique du texte ↗") }
            TextButton(onClick={open(context,"https://creativecommons.org/licenses/by-sa/4.0/deed.fr")}) { Text("Licence du texte Wikipédia ↗") }
        }
        if(m.latitude!=null) OutlinedButton(onClick=onMap,modifier=Modifier.fillMaxWidth()) { Text("Voir sur la carte") }
        image?.let {
            Text("Photo : ${it.author.ifBlank { "auteur indiqué sur la source" }} · ${it.license}",style=MaterialTheme.typography.bodySmall)
            TextButton(onClick={open(context,it.page)}) { Text("Source de la photographie ↗") }
            if(it.licenseUrl.isNotBlank()) TextButton(onClick={open(context,it.licenseUrl)}) { Text("Licence de la photographie ↗") }
        }
        Text("${m.reference} · Ministère de la Culture\nScores : ${m.scoreSource}",style=MaterialTheme.typography.bodySmall,color=MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

private fun communeLabel(value: String): String {
    val communes=value.split(';').map { it.trim() }.filter { it.isNotBlank() }.distinct()
    return if(communes.size<=1) value else "${communes.first()} et ${communes.size-1} autre${if(communes.size==2) "" else "s"} commune${if(communes.size==2) "" else "s"}"
}

@Composable private fun Score(label: String,value: Int,modifier: Modifier) {
    Surface(modifier,shape=RoundedCornerShape(12.dp),color=MaterialTheme.colorScheme.surfaceContainer) {
        Column(Modifier.padding(10.dp),horizontalAlignment=Alignment.CenterHorizontally) {
            Text(if(value < 0) "—" else "$value",style=MaterialTheme.typography.titleLarge,fontWeight=FontWeight.Medium)
            Text(label,style=MaterialTheme.typography.labelSmall)
        }
    }
}
private fun open(context: Context,url: String,chooser: Boolean=false) {
    val uri=Uri.parse(url)
    if(uri.scheme !in setOf("https","http","geo")) return
    try {
        val intent=Intent(Intent.ACTION_VIEW,uri)
        if(chooser && intent.resolveActivity(context.packageManager)==null) {
            Toast.makeText(context,"Aucune application d’itinéraire n’est installée.",Toast.LENGTH_LONG).show()
            return
        }
        context.startActivity(if(chooser) Intent.createChooser(intent,"Ouvrir l’itinéraire avec") else intent)
    } catch(_: ActivityNotFoundException) { Toast.makeText(context,"Aucune application compatible n’est installée.",Toast.LENGTH_LONG).show() }
      catch(_: SecurityException) { Toast.makeText(context,"Ce lien n’a pas pu être ouvert.",Toast.LENGTH_LONG).show() }
}

