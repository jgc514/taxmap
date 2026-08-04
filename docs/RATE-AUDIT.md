# Tax-rate audit — map vs. county appraisal districts

Sources: the 2025 Comptroller PTAD rates-and-levies workbook, the
rate sheets published on all 254 CAD websites (`scrub_cad_rates.py`),
and the rates the map itself renders (`parcels_rated`).

## Summary

* **374 emergency services districts across 95 counties are missing from every parcel rate.**
  The Comptroller workbook already carries each one's adopted rate — the
  map drops them because `gen_recipes.py` only adds a special district to
  a county's base stack when it can prove the district covers the whole
  county, and ESD boundaries are not published statewide.
* 1 county's own published area totals include an ESD in **every** area, which proves county-wide coverage: Blanco.
* 0 counties publish areas both with and without an ESD, so those need real boundaries.
* The remaining counties publish no area totals we could parse; see `RATE-FIX-ROUTES.md` for where their coverage data can be obtained.

## 1. Counties where the map omits an ESD

`coverage` is read off the CAD's own published area totals, not guessed:
*countywide* = every published area includes an ESD; *partial* = some do
not; *unknown* = that CAD publishes no area totals we could parse.

| County | ESDs | rate range | coverage | on CAD site | map understates by |
|---|---:|---|---|---:|---:|
| Harris | 32 | 0.0300–0.1000 | unknown | 0/32 |  |
| Bastrop | 5 | 0.1000–0.7510 | unknown | 1/5 |  |
| Hardin | 8 | 0.0250–0.8014 | unknown | 0/8 |  |
| Travis | 17 | 0.0266–0.1000 | unknown | 0/17 |  |
| Williamson | 12 | 0.0745–0.1000 | unknown | 0/12 |  |
| Bexar | 12 | 0.0646–0.1000 | unknown | 0/12 |  |
| Montgomery | 10 | 0.0922–0.1000 | unknown | 0/10 |  |
| Ellis | 12 | 0.0255–0.1000 | unknown | 0/12 |  |
| Fort Bend | 10 | 0.0657–0.1000 | unknown | 9/10 |  |
| Hamilton | 1 | 0.8377–0.8377 | unknown | 0/1 |  |
| Harrison | 9 | 0.0538–0.1000 | unknown | 0/9 |  |
| Burnet | 9 | 0.0141–0.1000 | unknown | 0/9 |  |
| Hays | 9 | 0.0500–0.1000 | unknown | 6/9 |  |
| Henderson | 11 | 0.0300–0.1000 | unknown | 0/11 |  |
| Parker | 6 | 0.0960–0.1000 | unknown | 0/6 | 0.1160 |
| Hidalgo | 6 | 0.0068–0.3000 | unknown | 0/6 |  |
| Kaufman | 7 | 0.0460–0.1000 | unknown | 0/7 |  |
| Medina | 6 | 0.0521–0.1000 | unknown | 1/6 |  |
| Comal | 7 | 0.0484–0.0998 | unknown | 0/7 |  |
| Nueces | 6 | 0.0300–0.1000 | unknown | 0/6 |  |
| Caldwell | 5 | 0.0884–0.1000 | unknown | 0/5 |  |
| Wilson | 5 | 0.0775–0.1000 | unknown | 5/5 |  |
| Brazoria | 6 | 0.0494–0.1000 | unknown | 0/6 |  |
| Brazos | 4 | 0.0217–0.2464 | unknown | 0/4 |  |
| Jim Hogg | 1 | 0.3836–0.3836 | unknown | 0/1 |  |
| Cass | 4 | 0.0903–0.1000 | unknown | 0/4 |  |
| Leon | 4 | 0.0867–0.1019 | unknown | 4/4 |  |
| Orange | 4 | 0.0729–0.1000 | unknown | 0/4 |  |
| Tyler | 8 | 0.0300–0.1000 | unknown | 0/8 |  |
| Llano | 5 | 0.0267–0.1000 | unknown | 0/5 |  |
| Van Zandt | 4 | 0.0500–0.1000 | unknown | 0/4 |  |
| Bowie | 6 | 0.0236–0.1000 | unknown | 0/6 |  |
| Jefferson | 5 | 0.0127–0.0991 | unknown | 0/5 |  |
| Falls | 3 | 0.0971–0.1000 | unknown | 0/3 |  |
| Wharton | 4 | 0.0500–0.0878 | unknown | 0/4 |  |
| Delta | 1 | 0.2686–0.2686 | unknown | 0/1 |  |
| Walker | 3 | 0.0600–0.1000 | unknown | 3/3 |  |
| Gregg | 3 | 0.0781–0.1000 | unknown | 3/3 |  |
| Wise | 3 | 0.0300–0.1000 | unknown | 0/3 |  |
| Kerr | 4 | 0.0122–0.1000 | unknown | 0/4 |  |
| Newton | 5 | 0.0300–0.0600 | unknown | 0/5 |  |
| Nacogdoches | 5 | 0.0213–0.1000 | unknown | 0/5 |  |
| Atascosa | 2 | 0.1000–0.1000 | unknown | 0/2 |  |
| Blanco | 2 | 0.1000–0.1000 | countywide | 2/2 | 0.1000 |
| Carson | 2 | 0.1000–0.1000 | unknown | 0/2 |  |
| San Jacinto | 2 | 0.1000–0.1000 | unknown | 0/2 |  |
| Austin | 3 | 0.0300–0.0931 | unknown | 3/3 |  |
| Jim Wells | 2 | 0.0949–0.0964 | unknown | 0/2 |  |
| Jackson | 3 | 0.0290–0.1000 | unknown | 0/3 |  |
| Liberty | 4 | 0.0279–0.1000 | unknown | 0/4 |  |
| El Paso | 2 | 0.0871–0.1000 | unknown | 0/2 |  |
| Hudspeth | 2 | 0.0884–0.0944 | unknown | 0/2 |  |
| Reeves | 2 | 0.0827–0.0901 | unknown | 0/2 |  |
| Upshur | 2 | 0.0700–0.1000 | unknown | 0/2 |  |
| Uvalde | 2 | 0.0712–0.0987 | unknown | 0/2 |  |
| Denton | 2 | 0.0600–0.1000 | unknown | 0/2 |  |
| Ector | 2 | 0.0800–0.0800 | unknown | 0/2 |  |
| Duval | 2 | 0.0725–0.0799 | unknown | 0/2 |  |
| Galveston | 2 | 0.0600–0.0855 | unknown | 0/2 |  |
| Smith | 2 | 0.0689–0.0696 | unknown | 2/2 |  |
| Bell | 1 | 0.1000–0.1000 | unknown | 1/1 |  |
| Coke | 1 | 0.1000–0.1000 | unknown | 0/1 |  |
| Gaines | 1 | 0.1000–0.1000 | unknown | 0/1 |  |
| Real | 1 | 0.1000–0.1000 | unknown | 0/1 |  |
| Waller | 1 | 0.1000–0.1000 | unknown | 1/1 |  |
| Houston | 2 | 0.0337–0.0643 | unknown | 0/2 |  |
| Clay | 2 | 0.0420–0.0557 | unknown | 2/2 |  |
| Jasper | 4 | 0.0181–0.0300 | unknown | 0/4 |  |
| Crane | 1 | 0.0923–0.0923 | unknown | 0/1 |  |
| Kenedy | 1 | 0.0910–0.0910 | unknown | 0/1 |  |
| Gonzales | 2 | 0.0251–0.0645 | unknown | 0/2 |  |
| Milam | 1 | 0.0890–0.0890 | unknown | 0/1 |  |
| Upton | 2 | 0.0043–0.0784 | unknown | 0/2 |  |
| Rusk | 1 | 0.0763–0.0763 | unknown | 1/1 |  |
| Rains | 1 | 0.0759–0.0759 | unknown | 0/1 |  |
| Tarrant | 1 | 0.0743–0.0743 | unknown | 0/1 |  |
| Robertson | 1 | 0.0730–0.0730 | unknown | 0/1 |  |
| Limestone | 2 | 0.0322–0.0365 | unknown | 0/2 |  |
| Bee | 4 | 0.0055–0.0267 | unknown | 0/4 |  |
| Cameron | 1 | 0.0627–0.0627 | unknown | 0/1 | 0.1374 |
| Hill | 2 | 0.0300–0.0304 | unknown | 2/2 |  |
| Johnson | 1 | 0.0565–0.0565 | unknown | 0/1 |  |
| Roberts | 1 | 0.0555–0.0555 | unknown | 0/1 |  |
| Live Oak | 1 | 0.0478–0.0478 | unknown | 0/1 |  |
| Navarro | 1 | 0.0426–0.0426 | unknown | 0/1 |  |
| Wood | 1 | 0.0411–0.0411 | unknown | 0/1 |  |
| Bosque | 1 | 0.0310–0.0310 | unknown | 0/1 |  |
| Frio | 1 | 0.0300–0.0300 | unknown | 0/1 |  |
| Panola | 1 | 0.0300–0.0300 | unknown | 1/1 |  |
| Palo Pinto | 1 | 0.0285–0.0285 | unknown | 0/1 |  |
| Runnels | 1 | 0.0238–0.0238 | unknown | 0/1 |  |
| Willacy | 1 | 0.0236–0.0236 | unknown | 0/1 |  |
| Tom Green | 1 | 0.0202–0.0202 | unknown | 0/1 |  |
| Grimes | 1 | 0.0155–0.0155 | unknown | 1/1 |  |
| Karnes | 1 | 0.0110–0.0110 | unknown | 1/1 |  |

## 2. Published area totals the map does not reproduce

Each row is a combined rate the county publishes for a specific
area, decomposed back into the exact units that sum to it, then
compared with what the map shows for parcels in that same
city/school-district area.

| County | published area | CAD total | map shows | gap | missing unit |
|---|---|---:|---:|---:|---|
| Gillespie | In Fredericksburg, MUD1 | 2.274105 | 1.273927 | +1.000178 | Gillespie County MUD #1, Gillespie County WCID |
| Kendall | GKE/SBN/WCC/MML | 2.392900 | 1.3929 | +1.000000 | Miralomas MUD |
| Kendall | GKE/SBN/WCC/MCD | 2.042900 | 1.3929 | +0.650000 | Kendall County MUD #1 |
| Aransas | M&O I&S In MUD Dist located | 1.519179 | 1.1454 | +0.373779 |  |
| Kendall | GKE/SCF/WCC/WCF | 1.480906 | 1.3148 | +0.166106 |  |
| Cameron | IRH 031-911-02 RIO HONDO I.S.D | 1.341900 | 1.204458 | +0.137442 | Southmost Union College District |
| Parker | BR BROCK I.S.D | 1.242600 | 1.12664 | +0.115960 | Parker County ESD #1, Parker County ESD #3 |
| Blanco | Blanco in the City | 1.759488 | 1.659488 | +0.100000 | North Blanco County ESD |
| Blanco | Blanco out of the City | 1.349408 | 1.249408 | +0.100000 | North Blanco County ESD |
| Blanco | Johnson City in the City | 1.684508 | 1.584508 | +0.100000 | North Blanco County ESD |
| Blanco | Johnson City out of the City | 1.352208 | 1.252208 | +0.100000 | North Blanco County ESD |
| Aransas | M&O I&S County in RFISD Dist | 1.175999 | 1.1454 | +0.030599 |  |
| Aransas | NVD - ARANSAS CO NAVIGATION | 1.602474 | 1.571875 | +0.030599 |  |
| Terry | In City of Brownfield | 2.968748 | 2.941751 | +0.026997 | South Plains Underground WCD |
| Terry | In City of Meadow | 2.555056 | 2.528059 | +0.026997 | South Plains Underground WCD |
| Terry | In City of Wellman | 3.393126 | 3.366129 | +0.026997 | South Plains Underground WCD |

## 3. PTAD rate disagrees with the CAD's published rate

Only counties whose scraped sheet otherwise agrees with PTAD are
listed. These still need eyeballing before acting on them: a CAD
page that breaks a rate into M&O and I&S, or that shows several
tax years, can produce a row here that is not really a conflict.
The Comptroller workbook is the authority unless the CAD's own
adopted-rate sheet for 2025 says otherwise.

| County | unit | PTAD | CAD | delta |
|---|---|---:|---:|---:|
| Armstrong | Armstrong | 0.466181 | 0.321222 | -0.144959 |
| Atascosa | Atascosa | 0.482888 | 0.408738 | -0.074150 |
| Atascosa | Lytle | 0.439372 | 0.398363 | -0.041009 |
| Atascosa | Poteet | 0.948100 | 0.945801 | -0.002299 |
| Austin | Austin | 0.503770 | 0.354230 | -0.149540 |
| Austin | Sealy ISD | 0.990500 | 0.659200 | -0.331300 |
| Bastrop | Bastrop | 0.428700 | 0.466900 | +0.038200 |
| Bastrop | Bastrop ISD | 1.070000 | 1.371000 | +0.301000 |
| Bastrop | Elgin ISD | 1.223400 | 1.518300 | +0.294900 |
| Bastrop | McDade ISD | 0.955500 | 1.030000 | +0.074500 |
| Bastrop | Smithville ISD | 0.942500 | 1.348350 | +0.405850 |
| Bastrop | Bastrop County MUD #3 | 0.000000 | 1.000000 | +1.000000 |
| Bastrop | Bastrop County MUD #4 | 0.000000 | 1.000000 | +1.000000 |
| Bastrop | The Colony MUD #1E | 0.665000 | 0.850000 | +0.185000 |
| Bexar | Bexar | 0.299999 | 0.276331 | -0.023668 |
| Brazos | Brazos | 0.423059 | 0.419700 | -0.003359 |
| Briscoe | Silverton ISD | 0.938200 | 0.271300 | -0.666900 |
| Camp | Camp | 0.422737 | 0.292737 | -0.130000 |
| Castro | Castro | 0.523900 | 0.432220 | -0.091680 |
| Collingsworth | Collingsworth | 0.817475 | 0.639680 | -0.177795 |
| Cottle | Cottle | 0.863600 | 0.718700 | -0.144900 |
| Crosby | Crosby | 0.686035 | 0.581035 | -0.105000 |
| Crosby | Crosbyton CISD | 1.074700 | 0.712200 | -0.362500 |
| Dallas | Addison | 0.608100 | 0.609822 | +0.001722 |
| Dallas | Carrollton | 0.537500 | 0.538750 | +0.001250 |
| Dallas | Cockrell Hill | 0.675743 | 0.695086 | +0.019343 |
| Dallas | Coppell | 0.444976 | 0.458632 | +0.013656 |
| Dallas | Duncanville | 0.600166 | 0.614834 | +0.014668 |
| Dallas | Glenn Heights | 0.562795 | 0.565015 | +0.002220 |
| Dallas | Highland Park | 0.199296 | 0.208550 | +0.009254 |
| Dallas | Lancaster | 0.599490 | 0.604606 | +0.005116 |
| Dallas | University Park | 0.218565 | 0.229964 | +0.011399 |
| Dallas | Carrollton-Farmers Branch ISD | 0.948100 | 0.983600 | +0.035500 |
| Dallas | Coppell ISD | 0.981900 | 1.002600 | +0.020700 |
| Dallas | Dallas ISD | 0.993835 | 0.997235 | +0.003400 |
| Dallas | Highland Park ISD | 0.834700 | 0.866900 | +0.032200 |
| Dallas | Valwood Improvement Authority | 0.040000 | 0.060000 | +0.020000 |
| Dallas | Wilmer MUD #1 | 0.180000 | 0.212500 | +0.032500 |
| DeWitt | Dewitt | 0.385760 | 0.355760 | -0.030000 |
| Dickens | Spur ISD | 0.992500 | 0.682200 | -0.310300 |
| Eastland | Eastland ISD | 0.786900 | 0.666900 | -0.120000 |
| Erath | Erath | 0.381100 | 0.285600 | -0.095500 |
| Fayette | Fayette | 0.409840 | 0.008000 | -0.401840 |
| Gaines | Gaines | 0.523555 | 0.361795 | -0.161760 |
| Hardeman | Chillicothe ISD | 0.824700 | 0.669200 | -0.155500 |
| Haskell | Paint Creek ISD | 0.869200 | 0.669200 | -0.200000 |
| Henderson | Seven Points | 0.240000 | 0.274383 | +0.034383 |
| Henderson | Trinidad | 0.478944 | 0.481501 | +0.002557 |
| Henderson | Henderson | 0.331493 | 0.274289 | -0.057204 |
| Hill | Hill | 0.452647 | 0.387769 | -0.064878 |
| Hopkins | Cumby | 0.349107 | 0.350572 | +0.001465 |
| Kaufman | Kaufman | 0.415113 | 0.334478 | -0.080635 |
| Leon | Leon ISD | 0.754900 | 0.644900 | -0.110000 |
| Leon | S.E. Leon County ESD #1 | 0.091990 | 0.090000 | -0.001990 |
| Leon | S.W. Leon County ESD #2 | 0.086655 | 0.100000 | +0.013345 |
| Leon | N.E. Leon County ESD #4 | 0.101865 | 0.100000 | -0.001865 |
| Llano | Llano | 0.259530 | 0.538700 | +0.279170 |
| Llano | Llano County MUD #1 | 0.298023 | 0.152124 | -0.145899 |
| Marion | Marion | 0.535878 | 0.454402 | -0.081476 |
| Medina | D'Hanis ISD | 0.813740 | 0.920300 | +0.106560 |
| Medina | Medina | 0.443400 | 0.360400 | -0.083000 |
| Mitchell | Mitchell | 0.456451 | 0.336451 | -0.120000 |
| Moore | Moore | 0.483735 | 0.411175 | -0.072560 |
| Orange | Orange | 0.492847 | 0.867000 | +0.374153 |
| Orange | Pine Forest | 0.500000 | 0.050000 | -0.450000 |
| Palo Pinto | Palo Pinto | 0.282158 | 0.282843 | +0.000685 |
| Parker | Parker | 0.285070 | 0.235022 | -0.050048 |
| Parmer | Parmer | 0.377399 | 0.289772 | -0.087627 |
| Refugio | Woodsboro ISD | 1.233833 | 0.770200 | -0.463633 |
| Robertson | Robertson | 0.665050 | 0.454000 | -0.211050 |
| Rusk | Rusk | 0.544476 | 0.491491 | -0.052985 |
| San Jacinto | San Jacinto | 0.482910 | 0.332910 | -0.150000 |
| Tarrant | Richland Hills | 0.504796 | 0.497841 | -0.006955 |
| Taylor | Abilene | 0.754200 | 0.750600 | -0.003600 |
| Victoria | Quail Creek MUD | 0.159200 | 0.168600 | +0.009400 |
| Waller | Hempstead | 0.559215 | 0.510341 | -0.048874 |
| Waller | Royal ISD | 1.069917 | 0.711100 | -0.358817 |
| Waller | Waller County MUD #9B | 0.625250 | 0.740000 | +0.114750 |
| Washington | Washington | 0.464000 | 0.304000 | -0.160000 |
| Wheeler | Wheeler | 0.517240 | 0.362640 | -0.154600 |

## 4. Counties with no machine-readable rate sheet

The crawler reached the site but found no parsable table of
jurisdictions — mostly JavaScript-rendered county portals. These
need the Truth-in-Taxation vendor APIs or a manual pass.

Anderson, Andrews, Angelina, Bailey, Bandera, Baylor, Bee, Borden, Bowie, Burleson, Caldwell, Calhoun, Callahan, Childress, Coleman, Collin, Comal, Cooke, Coryell, Denton, Ector, Edwards, El Paso, Ellis, Fannin, Floyd, Goliad, Guadalupe, Hamilton, Harris, Harrison, Hidalgo, Hudspeth, Hunt, Jackson, Jasper, Jeff Davis, Jim Hogg, Jim Wells, Kenedy, Kerr, Kimble, Knox, La Salle, Lampasas, Limestone, Lipscomb, Live Oak, Lubbock, Mason, Matagorda, Maverick, McLennan, McMullen, Montgomery, Nacogdoches, Navarro, Newton, Nueces, Ochiltree, Pecos, Polk, Potter, Presidio, Randall, Reeves, Roberts, Rockwall, San Augustine, Stephens, Throckmorton, Tom Green, Travis, Trinity, Val Verde, Van Zandt, Webb, Wharton, Wichita, Wilbarger, Williamson, Winkler, Yoakum, Zapata, Zavala
