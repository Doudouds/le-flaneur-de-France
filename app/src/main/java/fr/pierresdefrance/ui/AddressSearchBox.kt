package fr.pierresdefrance.ui

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.unit.dp

@Composable
fun AddressSearchBox(state: DiscoveryState,vm: DiscoveryViewModel) {
    val focus=LocalFocusManager.current
    fun submit() { focus.clearFocus(); vm.searchAddress() }
    OutlinedTextField(value=state.addressQuery,onValueChange=vm::editAddress,
        label={Text("Adresse ou ville")},singleLine=true,modifier=Modifier.fillMaxWidth(),
        keyboardOptions=KeyboardOptions(imeAction=ImeAction.Search),
        keyboardActions=KeyboardActions(onSearch={submit()}),
        trailingIcon={
            Row {
                if(state.addressQuery.isNotEmpty()) IconButton(onClick={vm.editAddress("")}) {
                    Icon(Icons.Default.Close,"Effacer l’adresse")
                }
                IconButton(onClick={submit()},enabled=!state.addressSearching && state.addressQuery.trim().length>=3) {
                    Icon(Icons.Default.Search,"Rechercher une adresse")
                }
            }
        })
    if(state.addressSearching) LinearProgressIndicator(Modifier.fillMaxWidth().padding(top=8.dp))
    if(state.addressResults.isNotEmpty()) {
        Column(Modifier.heightIn(max=240.dp).verticalScroll(rememberScrollState())) {
            state.addressResults.forEach { place ->
                Column(Modifier.fillMaxWidth().clickable { focus.clearFocus(); vm.usePlace(place) }
                    .padding(vertical=12.dp)) {
                    Text(place.label,style=MaterialTheme.typography.bodyMedium)
                    if(place.context.isNotBlank()) Text(place.context,style=MaterialTheme.typography.bodySmall,
                        color=MaterialTheme.colorScheme.onSurfaceVariant)
                }
                HorizontalDivider()
            }
        }
        Text("Adresses : IGN · Base Adresse Nationale",style=MaterialTheme.typography.labelSmall)
    }
    state.addressMessage?.let { Text(it,Modifier.padding(top=8.dp),style=MaterialTheme.typography.bodySmall) }
}
