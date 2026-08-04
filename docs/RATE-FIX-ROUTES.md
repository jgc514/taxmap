# Closing the ESD gap — what data exists, county by county

Every ESD's *rate* is already in the Comptroller workbook we build from.
What is missing is *coverage*: which parcels are inside which district.
These are the routes to that, ranked by how exact they are.

* **1** counties can be fixed from the CAD's own published area totals today.
* **53** more advertise a downloadable appraisal roll or data export — the exact per-parcel unit stack, through the parser that already handles Wilson/Bandera/Guadalupe.
* **9** more have a published ESD/fire-district boundary layer on ArcGIS.
* **32** have none of the three and need a public-information request.

| County | ESDs | max rate | route 1: CAD area totals | route 2: roll/data export | route 3: ArcGIS ESD layer |
|---|---:|---:|---|---|---|
| [Hamilton](https://www.hamiltoncad.org/) | 1 | 0.8377 | unknown | — | — |
| [Hardin](https://www.hardin-cad.org/) | 8 | 0.8014 | unknown | data download | HardinCADWebService |
| [Bastrop](https://www.bastropcad.org/) | 5 | 0.7510 | unknown | appraisal roll, data download | — |
| [Jim Hogg](https://www.jimhogg-cad.org/) | 1 | 0.3836 | unknown | appraisal roll | — |
| [Hidalgo](https://www.hidalgoad.org/) | 6 | 0.3000 | unknown | — | — |
| [Delta](https://www.delta-cad.org/) | 1 | 0.2686 | unknown | — | — |
| [Brazos](https://www.brazoscad.org/) | 4 | 0.2464 | unknown | data download | — |
| [Leon](https://www.leoncad.org/) | 4 | 0.1019 | unknown | appraisal roll | — |
| [Atascosa](https://www.atascosacad.com/) | 2 | 0.1000 | unknown | appraisal roll, data export | Atascosa County ESD 1 |
| [Bell](https://bellcad.org/) | 1 | 0.1000 | unknown | appraisal roll, certified roll | — |
| [Bexar](https://bcad.org/) | 12 | 0.1000 | unknown | appraisal roll | Bexar And Local Municipalities Fire Stations |
| [Blanco](https://blancocad.com/) | 2 | 0.1000 | solved | — | — |
| [Bowie](https://bowieappraisal.com/) | 6 | 0.1000 | unknown | — | — |
| [Brazoria](https://www.brazoriacad.org/) | 6 | 0.1000 | unknown | appraisal roll, data download | — |
| [Burnet](https://burnet-cad.org/) | 9 | 0.1000 | unknown | appraisal roll, certified roll | — |
| [Caldwell](https://caldwellcad.org/) | 5 | 0.1000 | unknown | appraisal export, data export, export data | Caldwell_CAD_Parcel_Map_Public |
| [Carson](https://www.carsoncad.org/) | 2 | 0.1000 | unknown | appraisal roll | — |
| [Cass](https://casscad.org/) | 4 | 0.1000 | unknown | — | — |
| [Coke](https://cokecad.org/) | 1 | 0.1000 | unknown | — | — |
| [Denton](https://www.dentoncad.com/) | 2 | 0.1000 | unknown | — | Denton_060326_WFL1 |
| [El Paso](https://epcad.org/) | 2 | 0.1000 | unknown | appraisal roll | — |
| [Ellis](https://www.elliscad.com/) | 12 | 0.1000 | unknown | — | — |
| [Falls](https://fallscad.net/) | 3 | 0.1000 | unknown | — | — |
| [Fort Bend](https://www.fbcad.org/) | 10 | 0.1000 | unknown | appraisal roll | — |
| [Gaines](https://gainescad.org/) | 1 | 0.1000 | unknown | data download | — |
| [Gregg](https://www.gcad.org/) | 3 | 0.1000 | unknown | appraisal roll | GreggRuskESDMap |
| [Harris](https://hcad.org/) | 32 | 0.1000 | unknown | appraisal roll, public data | — |
| [Harrison](https://harrisoncad.net/) | 9 | 0.1000 | unknown | — | — |
| [Hays](https://hayscad.com/) | 9 | 0.1000 | unknown | appraisal roll, data download | — |
| [Henderson](https://henderson-cad.org/) | 11 | 0.1000 | unknown | — | — |
| [Jackson](https://jacksoncad.org/) | 3 | 0.1000 | unknown | appraisal roll, certified roll | — |
| [Kaufman](https://www.kaufman-cad.org/) | 7 | 0.1000 | unknown | data export | — |
| [Kerr](https://kerrcad.org/) | 4 | 0.1000 | unknown | appraisal export | — |
| [Liberty](https://libertycad.com/) | 4 | 0.1000 | unknown | appraisal roll | LibertyCADWebService_AdditionalLayers |
| [Llano](https://llanocad.net/) | 5 | 0.1000 | unknown | — | LlanoCADAdditionalData |
| [Medina](https://medinacad.org/) | 6 | 0.1000 | unknown | — | MedinaCADWebService |
| [Montgomery](https://www.mcad-tx.org/) | 10 | 0.1000 | unknown | — | — |
| [Nacogdoches](https://nacocad.org/) | 5 | 0.1000 | unknown | appraisal roll | — |
| [Nueces](https://nuecescad.net/) | 6 | 0.1000 | unknown | — | NuecesCADWebService |
| [Orange](https://orangecad.net/) | 4 | 0.1000 | unknown | appraisal roll, data download | OrangeCADWebService |
| [Parker](https://iswdataclient.azurewebsites.net/webindex.aspx?dbkey=PARKERCAD&#038;time=202405030102026) | 6 | 0.1000 | unknown | — | ParkerCADAdditionalData |
| [Real](https://realcad.org/) | 1 | 0.1000 | unknown | appraisal roll | RealCADAdditionalLayers |
| [San Jacinto](https://sjcad.org/) | 2 | 0.1000 | unknown | appraisal roll, certified roll | — |
| [Travis](https://traviscad.org/) | 17 | 0.1000 | unknown | — | — |
| [Tyler](https://www.tylercad.net) | 8 | 0.1000 | unknown | appraisal roll | Emergency Service Districts |
| [Upshur](https://upshur-cad.org/) | 2 | 0.1000 | unknown | — | — |
| [Van Zandt](https://vzcad.org/) | 4 | 0.1000 | unknown | — | VanZandtCADAdditionalData |
| [Walker](https://walkercad.org/) | 3 | 0.1000 | unknown | — | WalkerCADWebService |
| [Waller](https://waller-cad.org/) | 1 | 0.1000 | unknown | — | — |
| [Williamson](https://www.wcad.org/) | 12 | 0.1000 | unknown | appraisal roll, certified roll, export data | — |
| [Wilson](https://wilson-cad.org/) | 5 | 0.1000 | unknown | — | — |
| [Wise](https://wise-cad.com/) | 3 | 0.1000 | unknown | data download | WiseCADWebService |
| [Comal](https://comalad.org/) | 7 | 0.0998 | unknown | — | — |
| [Jefferson](https://jcad.org/) | 5 | 0.0991 | unknown | appraisal roll | — |
| [Uvalde](https://uvaldecad.org/) | 2 | 0.0987 | unknown | appraisal roll | — |
| [Jim Wells](https://www.jimwellscad.org/) | 2 | 0.0964 | unknown | — | — |
| [Hudspeth](https://hudspethcad.org/) | 2 | 0.0944 | unknown | appraisal roll | — |
| [Austin](https://www.austincad.org/) | 3 | 0.0931 | unknown | appraisal roll | Pflugerville Area ESD Boundaries_WFL1 |
| [Crane](https://www.cranecad.org/) | 1 | 0.0923 | unknown | appraisal roll | — |
| [Kenedy](https://kenedycad.org/) | 1 | 0.0910 | unknown | — | — |
| [Reeves](https://www.reevescountytax.org/) | 2 | 0.0901 | unknown | — | — |
| [Milam](https://milamad.org/) | 1 | 0.0890 | unknown | data download | — |
| [Wharton](https://www.whartoncad.net/) | 4 | 0.0878 | unknown | — | — |
| [Galveston](https://galvestoncad.org/) | 2 | 0.0855 | unknown | certified roll, export data, public data | — |
| [Ector](https://www.ectorcad.org/) | 2 | 0.0800 | unknown | — | — |
| [Duval](https://duvalcad.org/) | 2 | 0.0799 | unknown | — | — |
| [Upton](https://www.uptoncad.org/) | 2 | 0.0784 | unknown | appraisal roll | — |
| [Rusk](https://www.ruskcad.org) | 1 | 0.0763 | unknown | appraisal roll | GreggRuskESDMap |
| [Rains](https://rainscad.org/) | 1 | 0.0759 | unknown | appraisal roll, certified roll | — |
| [Tarrant](https://www.tad.org) | 1 | 0.0743 | unknown | data download | — |
| [Robertson](https://robertsoncad.com/) | 1 | 0.0730 | unknown | — | — |
| [Smith](https://www.smithcad.org/) | 2 | 0.0696 | unknown | — | — |
| [Gonzales](https://www.gonzalescad.org/) | 2 | 0.0645 | unknown | appraisal roll | — |
| [Houston](https://www.houstoncad.org/) | 2 | 0.0643 | unknown | appraisal roll | Houston Fire Districts |
| [Cameron](https://www.cameroncad.org/) | 1 | 0.0627 | unknown | — | — |
| [Newton](http://www.newtoncad.org) | 5 | 0.0600 | unknown | certified roll | — |
| [Johnson](https://johnsoncad.com/) | 1 | 0.0565 | unknown | data download | — |
| [Clay](https://www.claycad.org/) | 2 | 0.0557 | unknown | appraisal roll | — |
| [Roberts](https://robertscad.org/) | 1 | 0.0555 | unknown | appraisal roll, certified roll | — |
| [Live Oak](https://liveoakappraisal.com/) | 1 | 0.0478 | unknown | — | — |
| [Navarro](https://navarrocad.com/) | 1 | 0.0426 | unknown | — | — |
| [Wood](https://www.woodcad.net/) | 1 | 0.0411 | unknown | — | WoodCADWebService |
| [Limestone](https://limestonecad.com/) | 2 | 0.0365 | unknown | — | — |
| [Bosque](https://www.bosquecad.com/) | 1 | 0.0310 | unknown | — | — |
| [Hill](https://www.hillcad.org/) | 2 | 0.0304 | unknown | appraisal roll | HillCADWebService |
| [Frio](https://www.friocad.org/) | 1 | 0.0300 | unknown | appraisal roll, certified roll | — |
| [Jasper](https://jaspercad.org/) | 4 | 0.0300 | unknown | — | — |
| [Panola](https://www.panolacad.org/) | 1 | 0.0300 | unknown | appraisal roll | — |
| [Palo Pinto](https://iswdataclient.azurewebsites.net/webindex.aspx?dbkey=PALOPINTOCAD&#038;time=202405030059019) | 1 | 0.0285 | unknown | — | — |
| [Bee](https://www.beecad.org/) | 4 | 0.0267 | unknown | — | BeeCADAdditionalLayers |
| [Runnels](https://www.runnelscad.org) | 1 | 0.0238 | unknown | appraisal roll | — |
| [Willacy](https://willacycad.org/) | 1 | 0.0236 | unknown | — | — |
| [Tom Green](https://iswdataclient.azurewebsites.net/webindex.aspx?dbkey=TOMGREENCAD&#038;time=202405030221032) | 1 | 0.0202 | unknown | appraisal roll | — |
| [Grimes](https://grimescad.org/) | 1 | 0.0155 | unknown | appraisal roll | — |
| [Karnes](https://www.karnescad.org/) | 1 | 0.0110 | unknown | appraisal roll | — |

## ArcGIS ESD / fire-district layers found

| service | owner | layers | url |
|---|---|---|---|
| ATP GIS Map | shaunencarnacion | Esd Districts | https://services2.arcgis.com/D4saGHECICkCeoJm/arcgis/rest/services/FBCAD_ATP_GIS_Map/FeatureServer |
| Atascosa County ESD 1 | bis_atascosacad | Emergency Service District 1 | https://services8.arcgis.com/q1dyPay4QViMab9g/arcgis/rest/services/Atascosa_County_ESD_1/FeatureServer |
| AtascosaESD1 | bis_atascosaesd1 | Atascosa County ESD 1 | https://services6.arcgis.com/zJpfZIJSQbEFs4Ch/arcgis/rest/services/AtascosaESD1/FeatureServer |
| AttascosaCADESD2 | bis_atascosacad | Emergency Service District 2 | https://services8.arcgis.com/q1dyPay4QViMab9g/arcgis/rest/services/AttascosaCADESD2/FeatureServer |
| BeeCADAdditionalLayers | bis_beecad | ESD | https://services3.arcgis.com/UCyyWODS30HHeveq/arcgis/rest/services/BeeCADAdditionalLayers/FeatureServer |
| Bexar And Local Municipalities Fire Stations | GIS@BEXAR.ORG | ESD Firestations | https://services1.arcgis.com/8onVmslF2KXErTHT/arcgis/rest/services/Bexar_And_Local_Municipalities_Fire_Stations/FeatureServer |
| Caldwell CAD Parcel Map | caldwellcad | Fire Districts, Emergency Service Districts | https://services.arcgis.com/rVxY74DxxIDrDbc0/arcgis/rest/services/Caldwell_CAD_Parcel_Map/FeatureServer |
| Caldwell County Fire Districts | caldwellcad | Fire Districts, Emergency Service Districts | https://services.arcgis.com/rVxY74DxxIDrDbc0/arcgis/rest/services/Caldwell_County_Fire_Districts/FeatureServer |
| Caldwell County Parcel Map | caldwellcad | Fire Districts, Emergency Service Districts | https://services.arcgis.com/rVxY74DxxIDrDbc0/arcgis/rest/services/Caldwell_County_Parcel_Map/FeatureServer |
| Caldwell_CAD_Parcel_Map_Public | bis_caldwellcad | Fire Districts, Emergency Service Districts | https://utility.arcgis.com/usrsvcs/servers/4911dd4ad22e4aae98ed02dab1c9e987/rest/services/Caldwell_CAD_Parcel_Map/FeatureServer |
| City and County Data | CityofJosephine | FireDistrict | https://services1.arcgis.com/x1h3avqp1HjU6Wyc/arcgis/rest/services/City_and_County_Data/FeatureServer |
| City of Vernon Web Service | bis_cityofvernontx | Fire District | https://services5.arcgis.com/YEy3wCyCT9X7HFbt/arcgis/rest/services/City_of_Vernon_Web_Service/FeatureServer |
| ComancheCADWebService | bis_comanchecad | Volunteer Fire Districts | https://services6.arcgis.com/gshWNaFhUNegaQZA/arcgis/rest/services/ComancheCADWebService/FeatureServer |
| ComancheCADWebService_Public | bis_comanchecad | Volunteer Fire Districts | https://utility.arcgis.com/usrsvcs/servers/7bf5a1b3daff4ebf9ce9e3bfe98dc676/rest/services/ComancheCADWebService/FeatureServer |
| Community Base Layers | COG_GIS_Admin | Fire District | https://services2.arcgis.com/uGo7PKALPg93ZiO2/arcgis/rest/services/Community_Base_Layers_WFL1/FeatureServer |
| DCSOMap042126_WFL1 | antoniakeddell | Fire Districts | https://services7.arcgis.com/uFAr0LUPy14bDaLg/arcgis/rest/services/DCSOMap042126_WFL1/FeatureServer |
| DCSO_Training_071326_WFL1 | patrick.corley_mark_43 | Fire Districts | https://services7.arcgis.com/uFAr0LUPy14bDaLg/arcgis/rest/services/DCSO_Training_071326_WFL1/FeatureServer |
| DentonCountyTraining_012026_WFL1 | patrick.corley_mark_43 | Fire Districts | https://services7.arcgis.com/uFAr0LUPy14bDaLg/arcgis/rest/services/DentonCountyTraining_012026_WFL1/FeatureServer |
| DentonMap121025_WFL1 | patrick.corley_mark_43 | Fire Districts | https://services7.arcgis.com/uFAr0LUPy14bDaLg/arcgis/rest/services/DentonMap121025_WFL1/FeatureServer |
| Denton_060326_WFL1 | patrick.corley_mark_43 | Fire Districts | https://services7.arcgis.com/uFAr0LUPy14bDaLg/arcgis/rest/services/Denton_060326_WFL1/FeatureServer |
| Denton_TX_WGS84_031226_WFL1 | emilykmark43 | Fire Districts | https://services7.arcgis.com/uFAr0LUPy14bDaLg/arcgis/rest/services/Denton_TX_WGS84_031226_WFL1/FeatureServer |
| DistrictsWebMap_WebLayer | Jesus.Pineda | HCAD ESD EMS, HCAD ESD FIRE | https://services.arcgis.com/su8ic9KbA7PYVxPS/arcgis/rest/services/DistrictsWebMap_WebLayer/FeatureServer |
| EA_Districts2a_WFL1 | pburkhart2 | Emergency Service Districts | https://services3.arcgis.com/dPuMck04cWB2fx4h/arcgis/rest/services/EA_Districts2a_WFL1/FeatureServer |
| EA_Districts3_WFL1 | pburkhart2 | ESD Voting Districts, Emergency Service Districts | https://services3.arcgis.com/dPuMck04cWB2fx4h/arcgis/rest/services/EA_Districts3_WFL1/FeatureServer |
| EA_Districts4_WFL1 | pburkhart2 | ESD Voting Districts, Emergency Service Districts | https://services3.arcgis.com/dPuMck04cWB2fx4h/arcgis/rest/services/EA_Districts4_WFL1/FeatureServer |
| EA_Districts5_WFL1 | pburkhart2 | ESD Voting Districts, Emergency Service Districts | https://services3.arcgis.com/dPuMck04cWB2fx4h/arcgis/rest/services/EA_Districts5_WFL1/FeatureServer |
| ESD | PD_libertyhill | ESD | https://services8.arcgis.com/qwMz1Ra8Qny9RDxC/arcgis/rest/services/ESD/FeatureServer |
| ESD Map Parker Co_WFL1 | Parker1_TACEO | ESD | https://services5.arcgis.com/FmxVFcLfGZgh8t6m/arcgis/rest/services/ESD_Map_Parker_Co_WFL1/FeatureServer |
| ESD Map W_Streets_WFL1 | Parker1_TACEO | ESD | https://services5.arcgis.com/FmxVFcLfGZgh8t6m/arcgis/rest/services/ESD_Map_W_Streets_WFL1/FeatureServer |
| ESD Parker County | Parker1_TACEO | ESD | https://services5.arcgis.com/FmxVFcLfGZgh8t6m/arcgis/rest/services/ESD_Parker_County/FeatureServer |
| ESD_3 | sneuman2012 | ESD 3 | https://services.arcgis.com/YZhxlqU7ABWQBGTG/arcgis/rest/services/ESD_3/FeatureServer |
| ElectionPrecinct_EmergencyServiceDistrictAmb | Julie_Sommerfeld | ElectionPrecinct_EmergencyServiceDistrictAmbulance | https://services3.arcgis.com/wdTkTU0MdZbNBEZy/arcgis/rest/services/ElectionPrecinct_EmergencyServiceDistrictAmbulance/FeatureServer |
| ElectionPrecinct_EmergencyServiceDistrictAmb | Julie_Sommerfeld | ElectionPrecinct_EmergencyServiceDistrictAmbulance | https://services3.arcgis.com/wdTkTU0MdZbNBEZy/arcgis/rest/services/ElectionPrecinct_EmergencyServiceDistrictAmbulance_view/FeatureServer |
| ElectionPrecinct_EmergencyServiceDistrictFir | Julie_Sommerfeld | ElectionPrecinct_EmergencyServiceDistrictFire | https://services3.arcgis.com/wdTkTU0MdZbNBEZy/arcgis/rest/services/ElectionPrecinct_EmergencyServiceDistrictFire/FeatureServer |
| ElectionPrecinct_EmergencyServiceDistrictFir | Julie_Sommerfeld | ElectionPrecinct_EmergencyServiceDistrictFire | https://services3.arcgis.com/wdTkTU0MdZbNBEZy/arcgis/rest/services/ElectionPrecinct_EmergencyServiceDistrictFire_view/FeatureServer |
| Emergency Service Districts | ldowney_911District | Emergency Service Districts | https://services5.arcgis.com/KgTmADyzXWOLUPKd/arcgis/rest/services/Emergency_Service_Districts/FeatureServer |
| Emergency Service Districts | hwahl_CityofTylerTexas | Emergency Service Districts | https://gis.cityoftyler.net/arcgis/rest/services/Emergency_Service_Districts/FeatureServer |
| Emergency Services | COG_GIS_Admin | Fire District | https://services2.arcgis.com/uGo7PKALPg93ZiO2/arcgis/rest/services/Emergency_Services/FeatureServer |
| Emergency Services Locations | COG_GIS_Admin | Fire District | https://services2.arcgis.com/uGo7PKALPg93ZiO2/arcgis/rest/services/Emergency_Services_Locations/FeatureServer |
| EmergencyServiceDistrict | Admin_BasCoGIS | EmergencyServiceDistrict | https://services3.arcgis.com/wdTkTU0MdZbNBEZy/arcgis/rest/services/EmergencyServiceDistrict/FeatureServer |
| Fire Districts | GIS.Data_MOCO | Fire Districts | https://services1.arcgis.com/PRoAPGnMSUqvTrzq/arcgis/rest/services/FireDistrict/FeatureServer |
| GreggRuskESDMap | ELVFDNJONES | Rusk Co ESD | https://services7.arcgis.com/h1Mc6DYU71QAXjtv/arcgis/rest/services/GreggRuskESDMap/FeatureServer |
| HardinCADWebService | bis_hardincad | ESD | https://services9.arcgis.com/8oveauLo4lI1NjDp/arcgis/rest/services/HardinCADWebService/FeatureServer |
| HardinCADWebService_Public | bis_hardincad | ESD | https://utility.arcgis.com/usrsvcs/servers/a858795cc1ec49fb87bad6295282a8b7/rest/services/HardinCADWebService/FeatureServer |
| Hazardous_Materials | dilberts | Non-Specialized Hazardous Materials First Response AFD and E | https://services1.arcgis.com/HGcSYZ5bvjRswoCb/arcgis/rest/services/Hazardous_Materials/FeatureServer |
| HillCADWebService | bis_hillcad | Emergency Services District 1, Emergency Services District 2 | https://services6.arcgis.com/c1IEzrw0UDP7bzay/arcgis/rest/services/HillCADWebService/FeatureServer |
| HillCADWebService_Public | bis_hillcad | Emergency Services District 1, Emergency Services District 2 | https://utility.arcgis.com/usrsvcs/servers/f91ed9bdaa3a4190976c7cd2bddc46c6/rest/services/HillCADWebService/FeatureServer |
| Houston Fire Districts | cohgis_ago | Houston Fire Districts | https://services.arcgis.com/NummVBqZSIJKUeVR/arcgis/rest/services/COH_Houston_Fire_Districts_view/FeatureServer |
| Layers for 311_WFL1 | CityofKyleGIS | Emergency Service Districts, Jurisdiction | https://services5.arcgis.com/Zhdeglqfvv6JnrnU/arcgis/rest/services/Layers_for_311_WFL1/FeatureServer |
| LibertyCADWebService_AdditionalLayers | bis_libertycad | Municipal Jurisdictions | https://services3.arcgis.com/LbQai106UcFy2LlR/arcgis/rest/services/LibertyCADWebService_AdditionalLayers/FeatureServer |
| LlanoCADAdditionalData | bis_llanocad | CAPCOG ESD Boundaries TOW, CAPCOG ESD Boundaries | https://services.arcgis.com/3fXpNNO2cx0O3RtY/arcgis/rest/services/LlanoCADAdditionalData/FeatureServer |
| MedinaCADWebService | bisconsulting | Emergency Service District | https://services6.arcgis.com/j94FvPaik4etwHFk/arcgis/rest/services/MedinaCADWebService/FeatureServer |
| Missouri City Zone Lookup_WFL1 | Matthew.Beavers@Missouricitytx.gov_MissouriCityTX | Fire Districts | https://services2.arcgis.com/6vRbgYSxztFGZwla/arcgis/rest/services/Missouri_City_Zone_Lookup_WFL1/FeatureServer |
| Northeast Volunteer Fire District (public vi | comadmin_comgis | Norhteast Volunteer Fire District Dispatch Area | https://services.arcgis.com/0H6bQdxd9223gQB5/arcgis/rest/services/Norhteast_Volunteer_Fire_District_Dispatch_Area_Collab/FeatureServer |
| NuecesCADWebService | bisconsulting | Emergency Fire District | https://services6.arcgis.com/j94FvPaik4etwHFk/arcgis/rest/services/NuecesCADWebService/FeatureServer |
| OrangeCADWebService | bis_orangecad | ESD Boundaries | https://services3.arcgis.com/HiTjmoyc4HjgiceA/arcgis/rest/services/OrangeCADWebService/FeatureServer |
| OrangeCADWebService_Public | bis_orangecad | ESD Boundaries | https://utility.arcgis.com/usrsvcs/servers/0e8d23989ce140c69b2962ae1da9b768/rest/services/OrangeCADWebService/FeatureServer |
| Other Jurisdictions | CityOfTaylorGIS | ESD | https://services7.arcgis.com/SQVxkeGOcRYhZqOD/arcgis/rest/services/Other_jurisdictions/FeatureServer |
| Other jurisdictions view | CityOfTaylorGIS | ESD | https://services7.arcgis.com/SQVxkeGOcRYhZqOD/arcgis/rest/services/Other_jurisdictions_View/FeatureServer |
| ParkerCADAdditionalData | bis_parkercad | ESD | https://services.arcgis.com/79g1H99xInKSRRK3/arcgis/rest/services/ParkerCADAdditionalData/FeatureServer |
| Pflugerville Area ESD Boundaries_WFL1 | EM3124@ausps.org_austin | Proposed ESD 2 Boundary, Current ESD 2 Boundary, Proposed ES | https://services.arcgis.com/0L95CJ0VTaxqcmED/arcgis/rest/services/Pflugerville_Area_ESD_Boundaries_WFL1/FeatureServer |
| Public Safety_Public | FBC_AGOAdmin | Emergency Service Districts | https://gisportal.fortbendcountytx.gov/arcgis/rest/services/InteractiveMap/Public_Safety_Public/FeatureServer |
| RealCADAdditionalLayers | bis_realcad | ESD | https://services5.arcgis.com/zYWSy8EH4fp8Icmp/arcgis/rest/services/RealCADAdditionalLayers/FeatureServer |
| VanZandtCADAdditionalData | bis_vanzandtcad | Fire Districts, Van Zandt ESD Zones | https://services5.arcgis.com/96Y3rGnOjGwKKDOM/arcgis/rest/services/VanZandtCADAdditionalData/FeatureServer |
| VanZandtCADWebService | bis_vanzandtcad | Fire Districts, Van Zandt ESD Zones | https://services5.arcgis.com/96Y3rGnOjGwKKDOM/arcgis/rest/services/VanZandtCADWebService/FeatureServer |
| VanZandtCADWebService_Public | bis_vanzandtcad | Fire Districts, Van Zandt ESD Zones | https://utility.arcgis.com/usrsvcs/servers/6507af9502de4fb19deb462399672684/rest/services/VanZandtCADWebService/FeatureServer |
| WalkerCADWebService | bis_walkercad | ESD | https://services6.arcgis.com/hEVWOxh6v1J8BInI/arcgis/rest/services/WalkerCADWebService/FeatureServer |
| WalkerCADWebService_Public | bis_walkercad | ESD | https://utility.arcgis.com/usrsvcs/servers/cc98400b3a414d6a9519d8c7ddf61ffc/rest/services/WalkerCADWebService/FeatureServer |
| WashingtonCADWebService | bis_washingtoncad | ESD | https://services3.arcgis.com/42lb4t0mpCcD1zg8/arcgis/rest/services/WashingtonCADWebService/FeatureServer |
| WashingtonCADWebService_Public | bis_washingtoncad | ESD | https://utility.arcgis.com/usrsvcs/servers/06c0f0c3ecbd41feb5ff104cb3c3b627/rest/services/WashingtonCADWebService/FeatureServer |
| WiseCADWebService | bis_wisecad | Fire Districts | https://services1.arcgis.com/9sR6E9qY5UqEzC5T/arcgis/rest/services/WiseCADWebService/FeatureServer |
| WiseCADWebService_Public | bis_wisecad | Fire Districts | https://utility.arcgis.com/usrsvcs/servers/49a1051e4fca4b1f9b1a8905e9d516f0/rest/services/WiseCADWebService/FeatureServer |
| WoodCADWebService | bis_woodcad | Fire Districts | https://services7.arcgis.com/5u6RvFtqihOOiyUO/arcgis/rest/services/WoodCADWebService/FeatureServer |
| WoodCADWebService_Public | bis_woodcad | Fire Districts | https://utility.arcgis.com/usrsvcs/servers/b444eae779694e10a8792a4a4798594a/rest/services/WoodCADWebService/FeatureServer |
| county_administrative_boundaries_view | esriadmin@wilco.org_WILCO | Emergency Service Districts | https://services.arcgis.com/5ZjkDcAQQjFnTEkh/arcgis/rest/services/county_administrative_boundaries_view/FeatureServer |
