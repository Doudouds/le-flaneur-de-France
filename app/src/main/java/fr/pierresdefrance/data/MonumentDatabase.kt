package fr.pierresdefrance.data

import androidx.room.*
import android.content.Context
import fr.pierresdefrance.BuildConfig

@Entity(tableName = "monuments", indices = [
    Index(value=["reference"], unique=true, name="index_monuments_reference"),
    Index(value=["searchName"], name="index_monuments_name"),
    Index(value=["commune"], name="index_monuments_commune"),
    Index(value=["department"], name="index_monuments_department"),
    Index(value=["latitude", "longitude", "id", "globalScore", "visualLevel"], name="index_monuments_coordinates")
])
data class MonumentDetail(
    @PrimaryKey val id: Long,
    val latitude: Double?,
    val longitude: Double?,
    val reference: String,
    val name: String,
    val alternativeName: String,
    val address: String,
    val commune: String,
    val insee: String,
    val department: String,
    val departmentName: String,
    val region: String,
    val protection: String,
    val protectionDates: String,
    val protectionDetails: String,
    val category: String,
    val description: String,
    val history: String,
    val period: String,
    val copyright: String,
    val shortDescription: String,
    val descriptionSource: String,
    val historySource: String,
    val popUrl: String,
    val wikipediaUrl: String,
    val imageUrl: String,
    val imagePageUrl: String,
    val imageAuthor: String,
    val imageLicense: String,
    val imageLicenseUrl: String,
    val scoreSource: String,
    val scoreEvidence: String,
    val coordinateStatus: String,
    val searchName: String,
    val searchText: String,
    val importance: Int,
    val notoriety: Int,
    val globalScore: Int,
    val visualLevel: Int,
 )

@Dao
interface MonumentDao {
    @Query("SELECT * FROM monuments WHERE id=:id")
    suspend fun detail(id: Long): MonumentDetail?
}

@Database(entities=[MonumentDetail::class], version=1, exportSchema=true)
abstract class MonumentDatabase : RoomDatabase() {
    abstract fun monuments(): MonumentDao
    companion object {
        fun open(context: Context): MonumentDatabase = Room.databaseBuilder(context.applicationContext,
            MonumentDatabase::class.java, "monuments-${BuildConfig.DATASET_REVISION}.db")
            .createFromAsset("monuments.db").build()
    }
}
