package fr.pierresdefrance.ui

import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.graphics.vector.PathParser
import androidx.compose.ui.unit.dp

/** Small native vector set; avoids shipping the complete extended Material icon catalogue. */
object HeritageIcons {
    private fun icon(name: String,path: String)=ImageVector.Builder(name,24.dp,24.dp,24f,24f).apply {
        addPath(pathData=PathParser().parsePathString(path).toNodes(),fill=SolidColor(Color.Black))
    }.build()
    val Monument=icon("Patrimoine","M2,9 L12,3 L22,9 Z M4,11 H7 V19 H4 Z M10.5,11 H13.5 V19 H10.5 Z M17,11 H20 V19 H17 Z M2,21 H22 V23 H2 Z")
    val Map=icon("Carte","M2,5 L8,2 L16,5 L22,2 V19 L16,22 L8,19 L2,22 Z M8,4.3 V17 L10,17.75 V5 Z M14,6.5 V19 L16,19.7 V7.2 Z")
    val Locate=icon("Ma position","M11,1 H13 V4.1 A8,8 0,0 1,19.9 11 H23 V13 H19.9 A8,8 0,0 1,13 19.9 V23 H11 V19.9 A8,8 0,0 1,4.1 13 H1 V11 H4.1 A8,8 0,0 1,11 4.1 Z M12,6 A6,6 0,1 0,12 18 A6,6 0,1 0,12 6 Z M12,9 A3,3 0,1 1,12 15 A3,3 0,1 1,12 9 Z")
    val Directions=icon("Itinéraire","M12,1 L23,12 L12,23 L1,12 Z M7,10 V16 H9 V12 H14 V15 L19,11 L14,7 V10 Z")
    val Chevron=icon("Ouvrir","M8,4 L16,12 L8,20 L6,18 L12,12 L6,6 Z")
}
