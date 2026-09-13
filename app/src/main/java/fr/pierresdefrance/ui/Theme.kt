package fr.pierresdefrance.ui

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp

private val light=lightColorScheme(primary=Color(0xFF42666C),onPrimary=Color.White,
    secondary=Color(0xFF786C59),secondaryContainer=Color(0xFFDCE7E5),onSecondaryContainer=Color(0xFF2B4C51),tertiary=Color(0xFF985F4C),background=Color(0xFFF8F6F1),
    surface=Color(0xFFF8F6F1),onSurface=Color(0xFF252D2C),surfaceContainer=Color(0xFFF0EDE5))
private val dark=darkColorScheme(primary=Color(0xFFA6C9CC),secondary=Color(0xFFD0C3AB),
    tertiary=Color(0xFFE4B19C),background=Color(0xFF191D1C),surface=Color(0xFF191D1C),onSurface=Color(0xFFE8E5DD))
@Composable fun HeritageTheme(content: @Composable ()->Unit) {
    MaterialTheme(colorScheme=if(isSystemInDarkTheme()) dark else light,
        typography=Typography(headlineLarge=TextStyle(fontFamily=FontFamily.Serif,fontSize=32.sp,lineHeight=38.sp),
            headlineMedium=TextStyle(fontFamily=FontFamily.Serif,fontSize=28.sp,lineHeight=34.sp),
            titleLarge=TextStyle(fontFamily=FontFamily.Serif,fontWeight=FontWeight.Medium,fontSize=23.sp,lineHeight=29.sp)),content=content)
}
