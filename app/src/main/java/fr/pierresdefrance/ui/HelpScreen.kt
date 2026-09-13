package fr.pierresdefrance.ui

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.List
import androidx.compose.material.icons.filled.Info
import androidx.compose.material.icons.filled.LocationOn
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.Star
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp

@Composable
fun HelpScreen() {
    Surface(
        modifier = Modifier.fillMaxSize(),
        color = MaterialTheme.colorScheme.background,
    ) {
        Column(
            Modifier
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .padding(20.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp),
        ) {
        Text("Aide", style = MaterialTheme.typography.headlineMedium)
        HorizontalDivider(thickness = 2.dp, color = MaterialTheme.colorScheme.outline)

        Text("Découvrir la France", style = MaterialTheme.typography.titleLarge)
        Text(
            "Le flâneur de France vous aide à repérer les monuments historiques, à les situer et à comprendre leur histoire. La localisation est facultative : vous pouvez explorer toute la France par la carte ou par la recherche.",
            style = MaterialTheme.typography.bodyLarge,
        )

        HelpCard(
            icon = HeritageIcons.Map,
            title = "Explorer la carte",
            text = "À faible zoom, les monuments proches sont regroupés. Zoomez pour faire apparaître les points, puis touchez un monument pour ouvrir sa fiche.",
        )
        HelpCard(
            icon = Icons.Default.LocationOn,
            title = "Utiliser ma position",
            text = "Le bouton de localisation recentre la carte et propose les monuments autour de vous. Si vous refusez l’autorisation, la carte et la recherche nationale restent disponibles.",
        )
        HelpCard(
            icon = Icons.Default.Search,
            title = "Rechercher une adresse",
            text = "Saisissez une ville, une adresse ou un code postal dans la barre de recherche, puis choisissez une suggestion pour explorer les monuments à proximité.",
        )

        Text("Carte et liste", style = MaterialTheme.typography.titleLarge)
        HelpIconDetail(
            icon = HeritageIcons.Map,
            label = "Carte",
            explanation = "Visualisez les monuments à l’échelle de la France et rapprochez-vous d’une zone pour voir les points individuellement.",
        )
        HelpIconDetail(
            icon = Icons.AutoMirrored.Filled.List,
            label = "Liste",
            explanation = "Consultez les monuments autour de votre position ou du lieu choisi. Une recherche par nom lance une recherche dans tout le catalogue français.",
        )

        Text("Comprendre une fiche monument", style = MaterialTheme.typography.titleLarge)
        Card(Modifier.fillMaxWidth()) {
            Column(
                Modifier.padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                Text("Une fiche peut contenir", style = MaterialTheme.typography.titleMedium)
                Text("• une photographie et sa source ;\n• une description et des repères historiques ;\n• la protection patrimoniale et sa période ;\n• des liens vers la fiche officielle POP ou Wikipédia ;\n• un itinéraire et l’emplacement sur la carte.", style = MaterialTheme.typography.bodyLarge)
                HorizontalDivider()
                Text("Les informations sont présentées avec leurs sources lorsqu’elles sont disponibles. Les coordonnées manquantes ou à vérifier sont signalées dans la fiche.", style = MaterialTheme.typography.bodyMedium)
            }
        }

        Text("Notation en étoiles", style = MaterialTheme.typography.titleLarge)
        Text(
            "Les étoiles donnent une indication relative de l’intérêt du monument pour la promenade. Elles combinent plusieurs indices patrimoniaux et documentaires ; elles ne constituent pas un classement absolu.",
            style = MaterialTheme.typography.bodyLarge,
        )
        RatingLegend(1, "Monument à découvrir", "Un lieu parfois discret, moins documenté ou d’intérêt plus local.", Color(0xFFF7B955))
        RatingLegend(2, "Intérêt notable", "Un monument qui mérite particulièrement le détour.", Color(0xFF64B5F6))
        RatingLegend(3, "Monument remarquable", "Un lieu particulièrement important, connu ou riche d’histoire.", Color(0xFF8E3A8A))

        Text("Données et connexion", style = MaterialTheme.typography.titleLarge)
        HelpIconDetail(
            icon = Icons.Default.Info,
            label = "Catalogue local",
            explanation = "Le catalogue des monuments est intégré à l’application pour permettre la consultation et la recherche par nom sans envoyer votre position.",
        )
        HelpIconDetail(
            icon = Icons.Default.Search,
            label = "Services en ligne",
            explanation = "La recherche d’adresse, les photographies et certains textes complémentaires nécessitent une connexion internet.",
        )
        Text("Les données patrimoniales proviennent notamment du Ministère de la Culture, d’OpenStreetMap et de Wikipédia. Consultez les liens affichés dans chaque fiche pour les détails et les licences.", style = MaterialTheme.typography.bodyMedium)
        }
    }
}

@Composable
private fun HelpCard(icon: androidx.compose.ui.graphics.vector.ImageVector, title: String, text: String) {
    Card(Modifier.fillMaxWidth()) {
        Row(
            Modifier.padding(16.dp),
            verticalAlignment = Alignment.Top,
            horizontalArrangement = Arrangement.spacedBy(14.dp),
        ) {
            Icon(icon, contentDescription = null, tint = MaterialTheme.colorScheme.primary, modifier = Modifier.size(28.dp))
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Text(title, style = MaterialTheme.typography.titleMedium)
                Text(text, style = MaterialTheme.typography.bodyLarge)
            }
        }
    }
}

@Composable
private fun HelpIconDetail(icon: androidx.compose.ui.graphics.vector.ImageVector, label: String, explanation: String) {
    Row(
        Modifier.fillMaxWidth(),
        verticalAlignment = Alignment.Top,
        horizontalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Icon(icon, contentDescription = null, tint = MaterialTheme.colorScheme.primary, modifier = Modifier.size(24.dp))
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Text(label, style = MaterialTheme.typography.labelLarge)
            Text(explanation, style = MaterialTheme.typography.bodyLarge)
        }
    }
}

@Composable
private fun RatingLegend(stars: Int, label: String, explanation: String, color: Color) {
    Card(
        Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = color.copy(alpha = 0.13f)),
    ) {
        Row(
            Modifier.padding(16.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(14.dp),
        ) {
            Icon(Icons.Default.Star, contentDescription = null, tint = color, modifier = Modifier.size(28.dp))
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                Text(starLabel(stars), color = color, style = MaterialTheme.typography.titleLarge)
                Text(label, style = MaterialTheme.typography.titleMedium)
                Text(explanation, style = MaterialTheme.typography.bodyMedium)
            }
        }
    }
}

private fun starLabel(stars: Int): String = "★".repeat(stars) + "☆".repeat(3 - stars)
