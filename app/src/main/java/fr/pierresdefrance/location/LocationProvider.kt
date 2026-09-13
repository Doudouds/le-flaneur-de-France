package fr.pierresdefrance.location

import android.annotation.SuppressLint
import android.content.Context
import android.os.SystemClock
import com.google.android.gms.location.*
import com.google.android.gms.tasks.CancellationTokenSource
import fr.pierresdefrance.domain.Position
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlin.coroutines.resume

class LocationProvider(context: Context) {
    private val client=LocationServices.getFusedLocationProviderClient(context)
    @SuppressLint("MissingPermission")
    suspend fun current(highAccuracy: Boolean=false): Position? = suspendCancellableCoroutine { cont ->
        val cancellation=CancellationTokenSource()
        cont.invokeOnCancellation { cancellation.cancel() }
        val request=CurrentLocationRequest.Builder()
            .setPriority(if(highAccuracy) Priority.PRIORITY_HIGH_ACCURACY else Priority.PRIORITY_BALANCED_POWER_ACCURACY)
            .setGranularity(Granularity.GRANULARITY_PERMISSION_LEVEL)
            .setMaxUpdateAgeMillis(60_000).setDurationMillis(15_000).build()
        try {
            client.getCurrentLocation(request,cancellation.token)
                .addOnSuccessListener { location ->
                    if(cont.isActive) cont.resume(location?.takeIf {
                        SystemClock.elapsedRealtimeNanos()-it.elapsedRealtimeNanos < 120_000_000_000 && it.accuracy<=5000
                    }?.let { Position(it.latitude,it.longitude) })
                }
                .addOnFailureListener { if(cont.isActive) cont.resume(null) }
        } catch(_: SecurityException) { if(cont.isActive) cont.resume(null) }
    }
}
