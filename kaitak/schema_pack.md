# Schema pack
Created 2026-11-20 22:54 by prepare_kaitak_data.py v1.0. Sample values are real records; there are only a few.

## HK UBEM Kai Tak.xlsx
- format: xlsx; size: 40,665 bytes; SHA-256: `117f035a546224d51aeee72e1933621f9bf0e5b9770c908c5bc81b7164eb4cf9`
- rows/features: 195
- licence/doc note: Your own selection list (derived from the HK-BFETD CSV).

| field | type | non-empty | examples |
|---|---|---|---|
| Floors_Count_地上层数 | text(raw stored value) | 195 | 6; 36; 26 |
| Height_m_建筑高度 | text(raw stored value) | 195 | 18; 108; 78 |
| UBEM_Main_Class_主类别 | text(raw stored value) | 195 | Residential_住宅类别; Mixed-use_混合用途; Mixed-use_混合用途 |
| UBEM_Sub_Class_子类别 | text(raw stored value) | 195 | Other Housing_其他房屋; Private Housing_私人房屋-Other Commercial_其他商业; Private Housing_私人房屋-Retail_零售 |
| UBEM_Mixed_Proportions_混合比例 | text(raw stored value) | 195 | Other Housing_其他房屋:1.00; Private Housing_私人房屋:0.77-Commercial_商业类别:0.23; Private Housing_私人房屋:0.77-Retail_零售:0.23 |
| Classification_Source_分类来源 | text(raw stored value) | 195 | Rule_Engine(LLM_Verified (Conf: 0.90)); Rule_Engine(GFA_Mixed); Rule_Engine(GFA_Mixed) |
| Classification_Notes_分类备注 | text(raw stored value) | 195 | Rule conclusion retained_保留规则确定性结论; Rule conclusion retained_保留规则确定性结论; Rule conclusion retained_保留规则确定性结论 |
| ML_Prediction_Confidence_机器学习置信度 | text(raw stored value) | 195 | 0.7576391331388549; 0.76972652212450499; 0.7409773276692292 |
| ML_Prob_Residential_住宅概率 | text(raw stored value) | 195 | 0.7576391331388549; 0.4568434212460178; 0.5165678276839047 |
| ML_Prob_Commercial_商业概率 | text(raw stored value) | 195 | 0.3354251775915364; 0.76972652212450499; 0.7409773276692292 |
| ML_Prob_Industrial_工业概率 | text(raw stored value) | 195 | 2.4278011952692899E-2; 2.9665929125558999E-3; 2.7455383652392998E-3 |
| LandsD_Structure_Type_地政署建筑类型 | text(raw stored value) | 195 | T; T; T |
| LandsD_Category_地政署分类 | text(raw stored value) | 195 | 1; 1; 1 |
| LandsD_Status_地政署状态 | text(raw stored value) | 195 | A; A; A |
| LandsD_Registered_GFA_地政署注册面积 | text(raw stored value) | 0 | ; ;  |
| LandsD_Building_Name_EN_地政署英文名 | text(raw stored value) | 195 | Kai Tak Building; Kai Tak Garden Block 2; Kai Tak Garden Block 3 |
| LandsD_Building_Name_TC_地政署中文名 | text(raw stored value) | 193 | 啓德大樓; 啓德花園第二座; 啓德花園第三座 |
| BDBIAR_Record_ID_屋宇署记录ID | text(raw stored value) | 45 | 22365; 15148; 15151 |
| BDBIAR_Classification_屋宇署分类 | text(raw stored value) | 45 | 住宅/綜合用途; 住宅/綜合用途; 住宅/綜合用途 |
| BDBIAR_Building_Age_Year_屋宇署楼龄年份 | text(raw stored value) | 45 | 1982; 1998; 1998 |
| Dist_to_BDBIAR_m_距屋宇署点位距离 | text(raw stored value) | 45 | 0; 0; 0 |
| Crowdsourced_POIs_Matched_众包POI匹配详情 | text(raw stored value) | 24 | ; 第二座 Block 2[apartments]; 屋企[landmark_and_historical_building] / 天祥顺德区美食[restaurant] / 第三座 Block 3[apartme |
| OSM_Record_ID_OSM记录ID | text(raw stored value) | 174 | ovt_9a2763da-87b7-48d0-bd6f-a038cbbad03a; 263472299; ovt_7d925b92-1450-4622-a7d9-fb829941ee95 |
| OSM_Building_Tag_OSM建筑标签 | text(raw stored value) | 155 | ; apartments;  |
| OSM_Amenity_Tag_OSM设施标签 | text(raw stored value) | 16 | beauty_salon; ; landmark_and_historical_building |
| OSM_Shop_Tag_OSM商铺标签 | text(raw stored value) | 3 | ; ;  |
| OZP_Zone_Code_法定图则代码 | text(raw stored value) | 192 | R(A); MRDJ; MRDJ |
| OZP_Zone_Desc_EN_法定图则英文描述 | text(raw stored value) | 192 | Residential (Group A); Major Road and Junction; Major Road and Junction |

## HK_UBEM_Buildings_Public_v1_1.csv
- format: csv; size: 130,327,699 bytes; SHA-256: `88bbe503517922697c52e4d448bfadeb7aa09209a500fad07229fa3dc37ef241`
- rows/features: 341153
- licence/doc note: Public record (Zenodo, HK-BFETD v1.1.0): CC BY 4.0 - not shipped in your folder; please confirm at the source.

| field | type | non-empty | examples |
|---|---|---|---|
| Building_ID_建筑ID | int | 341153 | 1; 10; 1000 |
| Footprint_Area_sqm_占地面积 | float | 341153 | 63.96772250185876; 18.54944524153712; 25.28503360670405 |
| Floors_Count_地上层数 | float | 341153 | 8.0; 7.0; 6.0 |
| Height_m_建筑高度 | float | 341153 | 25.5; 19.8; 16.9 |
| UBEM_Main_Class_主类别 | text | 341153 | Residential_住宅类别; Commercial_商业类别; Mixed-use_混合用途 |
| UBEM_Sub_Class_子类别 | text | 341153 | Private Housing_私人房屋; Other Commercial_其他商业; Private Housing_私人房屋-Restaurant_食肆-Retail_零售 |
| UBEM_Mixed_Proportions_混合比例 | text | 341153 | Private Housing_私人房屋:1.00; Other Commercial_其他商业:1.00; Private Housing_私人房屋:0.50-Other Commercial_其他商业:0.50 |
| Classification_Source_分类来源 | text | 341153 | Rule_Engine(OSM); Machine_Learning_Predicted; Rule_Engine(BDBIAR+GFA+Keyword+LandsD_Category+OSM) |
| Classification_Notes_分类备注 | text | 341153 | Rule conclusion retained_保留规则确定性结论; ML completion with regression-based subclass allocation_ML推断填补-ML回归精准分配(P=0.82); ML completion with regression-based subclass allocation_ML推断填补-ML回归精准分配(P=0.96) |
| ML_Prediction_Confidence_机器学习置信度 | float | 341153 | 0.9963701893307076; 0.823959376305186; 0.9571985257121616 |
| ML_Prob_Residential_住宅概率 | float | 341153 | 0.9963701893307076; 0.823959376305186; 0.0315422598531427 |
| ML_Prob_Commercial_商业概率 | float | 341153 | 0.0080897389331091; 0.3079434267905229; 0.9571985257121616 |
| ML_Prob_Industrial_工业概率 | float | 341153 | 0.0009820838375072; 0.0013632446278768; 0.0447967931900985 |
| LandsD_Structure_Type_地政署建筑类型 | text | 341153 | T; P |
| LandsD_Category_地政署分类 | int | 341153 | 9; 1; 3 |
| LandsD_Status_地政署状态 | text | 341153 | A |
| LandsD_Registered_GFA_地政署注册面积 | float | 41 | 439.94; 414.71; 276.99 |
| LandsD_Building_Name_EN_地政署英文名 | mixed(text,int) | 64779 | Yau Shing Building; Hong Kong Gold Coast Phase II Tower 32; Greenview Terrace Substation |
| LandsD_Building_Name_TC_地政署中文名 | text | 64324 | 志剛堂; 友成樓; 香港黃金海岸二期第３２座 |
| BDBIAR_Record_ID_屋宇署记录ID | float | 76544 | 41222.0; 8424.0; 11029.0 |
| BDBIAR_Classification_屋宇署分类 | text | 76544 | 住宅/綜合用途; 其他; 工業 |
| BDBIAR_Building_Age_Year_屋宇署楼龄年份 | float | 74691 | 2005.0; 1967.0; 1995.0 |
| Dist_to_BDBIAR_m_距屋宇署点位距离 | float | 76544 | 0.0; 0.6842878837798443; 0.3931435198918001 |
| Crowdsourced_POIs_Matched_众包POI匹配详情 | text | 15642 | 喜多郎日本料理[restaurant->食肆（Restaurant）]; 无命名POI; Sam Tung Uk Garden[botanical_garden] / Sam Tung Uk Museum[history_museum] |
| OSM_Record_ID_OSM记录ID | mixed(int,text) | 119015 | 1072944287; 1241138497; 112978946 |
| OSM_Building_Tag_OSM建筑标签 | text | 99311 | yes; house; apartments |
| OSM_Amenity_Tag_OSM设施标签 | text | 18395 | restaurant; charging_station; martial_arts_club |
| OSM_Shop_Tag_OSM商铺标签 | text | 3614 | retail; herbalist; office |
| OZP_Zone_Code_法定图则代码 | text | 309453 | V; MRDJ; G/IC |
| OZP_Zone_Desc_EN_法定图则英文描述 | text | 309455 | Village Type Development; Major Road and Junction; Government, Institution or Community |

## HK_UBEM_Buildings_Public_v1_1.geojson
- format: geojson; size: 781,727,720 bytes; SHA-256: `976463a6cd50d21bb9e9dab86bbd4936b5157e1790478d5c6cc731a7923e62ec`
- rows/features: 341153
- licence/doc note: Same as CSV: CC BY 4.0 per the Zenodo record; confirm at the source.
- CRS: urn:ogc:def:crs:EPSG::2326; looks like lon/lat: False; geometry types: {'Polygon': 341153}; extent: [801625.3058, 802048.102, 863009.3291, 846831.4404]

| field | type | non-empty | examples |
|---|---|---|---|
| Building_ID_建筑ID | int | 341153 | 130; 139; 161 |
| Footprint_Area_sqm_占地面积 | float | 341153 | 25.88498777666143; 25.095973517000864; 41.8015823801626 |
| Floors_Count_地上层数 | float | 341153 | 5.0; 6.0; 4.0 |
| Height_m_建筑高度 | float | 341153 | 14.7; 16.5; 12.6 |
| UBEM_Main_Class_主类别 | text | 341153 | Commercial_商业类别; Residential_住宅类别; Mixed-use_混合用途 |
| UBEM_Sub_Class_子类别 | text | 341153 | Office_办公室; Private Housing_私人房屋; Restaurant_食肆 |
| UBEM_Mixed_Proportions_混合比例 | text | 341153 | Office_办公室:1.00; Private Housing_私人房屋:1.00; Restaurant_食肆:1.00 |
| Classification_Source_分类来源 | text | 341153 | Rule_Engine(BDBIAR); Rule_Engine(BDBIAR+LandsD_Category); Rule_Engine(Keyword+OSM) |
| Classification_Notes_分类备注 | text | 341153 | Rule conclusion retained_保留规则确定性结论; ML completion with regression-based subclass allocation_ML推断填补-ML回归精准分配(P=0.98); ML completion with regression-based subclass allocation_ML推断填补-ML回归精准分配(P=0.95) |
| ML_Prediction_Confidence_机器学习置信度 | float | 341153 | 0.944426301660342; 0.9553498564966556; 0.9512175915491646 |
| ML_Prob_Residential_住宅概率 | float | 341153 | 0.1112690155135189; 0.0737289442173914; 0.0731008179207801 |
| ML_Prob_Commercial_商业概率 | float | 341153 | 0.944426301660342; 0.9553498564966556; 0.9512175915491646 |
| ML_Prob_Industrial_工业概率 | float | 341153 | 0.0295549012896557; 0.0421403674927222; 0.0196933747192234 |
| LandsD_Structure_Type_地政署建筑类型 | text | 341153 | T; P |
| LandsD_Category_地政署分类 | int | 341153 | 9; 1; 2 |
| LandsD_Status_地政署状态 | text | 341153 | A |
| LandsD_Registered_GFA_地政署注册面积 | float | 41 | 439.94; 414.71; 276.99 |
| LandsD_Building_Name_EN_地政署英文名 | mixed(text,int) | 64779 | SHUN LEE HOUSE; CAMBRIDGE PLAZA; Woodland Crest Block 1 |
| LandsD_Building_Name_TC_地政署中文名 | text | 64324 | 順利樓; 劍橋廣場; 奕翠園第一座 |
| BDBIAR_Record_ID_屋宇署记录ID | float | 76544 | 38222.0; 23863.0; 30949.0 |
| BDBIAR_Classification_屋宇署分类 | text | 76544 | 寫字樓/商業; 住宅/綜合用途; 工業 |
| BDBIAR_Building_Age_Year_屋宇署楼龄年份 | float | 74691 | 1980.0; 1973.0; 1991.0 |
| Dist_to_BDBIAR_m_距屋宇署点位距离 | float | 76544 | 23.50682277720508; 27.5855486438286; 22.215564426554632 |
| Crowdsourced_POIs_Matched_众包POI匹配详情 | text | 15642 | Café de Coral[restaurant->食肆（Restaurant）] / 利一食品[restaurant->食肆（Restaurant）]; 春記粉麵[restaurant->食肆（Restaurant）] / 好姐茶室[restaurant->食肆（Restaurant）] / 洪記茶室[resta; 炳華餐廳 Bing Hua Restaurant[restaurant] / 沙頭角餐廳 Sha Tau Kok Restaurant[restaurant]  |
| OSM_Record_ID_OSM记录ID | mixed(int,text) | 119015 | ovt_dc6df1ae-935b-41e5-b484-e97348cef967; 255289069; ovt_b8f38cab-d341-49a2-b9ea-f2800a839b7b |
| OSM_Building_Tag_OSM建筑标签 | text | 99311 | apartments; yes; residential |
| OSM_Amenity_Tag_OSM设施标签 | text | 18395 | automotive_parts_and_accessories; restaurant; landmark_and_historical_building |
| OSM_Shop_Tag_OSM商铺标签 | text | 3614 | hardware; massage; chemist |
| OZP_Zone_Code_法定图则代码 | text | 309453 | MRDJ; OU; R(C)2 |
| OZP_Zone_Desc_EN_法定图则英文描述 | text | 309455 | Major Road and Junction; Other Specified Uses; Residential (Group C)2 |

## Building_Outline_Public_v20261020_converted.gpkg
- format: geopackage; size: 194,662,400 bytes; SHA-256: `6330060a791731727e7123c65746532753a380b14dea3f3a0778bfe44f9f4d8a`
- rows/features: 
- licence/doc note: NOT FOUND locally. Check the Lands Department / CSDI Portal terms for this layer before publishing.
- layer `Building` (features): rows 342233, geometry GEOMETRY, CRS {'name': 'Hong Kong 1980 Grid System', 'authority': 'EPSG:2326', 'definition': 'PROJCS["Hong Kong 1980 Grid System",GEOGCS["Hong Kong 1980",DATUM["Hong_Kong_1980",SPHEROID["International 1924",6378388,297,AUTHORITY["EPSG","7022"]],AUTHORITY["EPSG","6611"]],PRIMEM["Greenwich",0,AUTHORITY["EPSG","8901"]],UNIT["degree",0.0174532925199433,AUTHORITY["EPSG","9122"]],AUTHORITY["EPSG",'}, extent [801625.3058400023, 802048.1020003249, 863009.329060001, 846831.4404003285]
- layer `BuildingLotNoInfo` (attributes): rows None, geometry None, CRS None, extent [None, None, None, None]
- layer `BuildingName` (attributes): rows None, geometry None, CRS None, extent [None, None, None, None]
- layer `BuildingRelateOPStructure` (attributes): rows None, geometry None, CRS None, extent [None, None, None, None]
- layer `BuildingWorksHistory` (attributes): rows None, geometry None, CRS None, extent [None, None, None, None]
- layer `OP` (attributes): rows None, geometry None, CRS None, extent [None, None, None, None]
- layer `OPStructure` (attributes): rows None, geometry None, CRS None, extent [None, None, None, None]

| field | type | non-empty | examples |
|---|---|---|---|
| id | integer | 342233 | 1; 2; 3 |
| OBJECTID | integer | 342233 | 1; 2; 3 |
| Shape_Length | real | 342233 | 58.57483675404797; 33.44676423055231; 6.322674431699736 |
| Shape_Area | real | 342233 | 171.27415305665085; 64.72754868859494; 2.4914199989660832 |
| GeoRefNo | text | 342233 | 2899032335; 2693332328; 2566932330 |
| DateCreate | text | 342233 | 2005-04-30T00:00:00.000; 2015-04-22T00:00:00.000; 2007-10-31T00:00:00.000 |
| BuildingBlockType | text | 342233 | Tower; Temporary Structure; Podium |
| BuildingCSUID | text | 342233 | 2899032335T20050430; 2693332328T20050430; 2566932330T20050430 |
| BuildingID | integer | 342233 | 1105760103; 1105760209; 1105760263 |
| Status | text | 342233 | Active |
| BuildingNameEN | text | 64668 | Kam Fuk Garden Block 8; Shun On Commercial Building; Lady Kadoorie Hostel |
| BuildingNameTC | text | 64224 | 錦福豪園第八座; 順安商業大廈; 嘉道理夫人宿舍 |
| BaseHeight | real | 235997 | 63.1; 19.9; 9.8 |
| TopHeight | real | 237399 | 66.6; 28.7; 12.5 |
| Storeys | integer | 60294 | 16; 34; 3 |
| StoreysInBasement | integer | 6513 | 1; 3; 2 |
| DateStamp | text | 342233 | 2013-07-12T00:00:00.000; 2015-04-22T00:00:00.000; 2016-03-30T00:00:00.000 |

## BDBIAR_BDBIAR_converted.csv
- format: csv; size: 17,944,164 bytes; SHA-256: `ba92cb092b51b20b02fbc7f4e95f7aa3ba8a4b714b39a4ade33887d4fe617115`
- rows/features: 51354
- licence/doc note: NOT FOUND locally. Check the data.gov.hk terms and data dictionary page for the Buildings Department dataset.

| field | type | non-empty | examples |
|---|---|---|---|
| OBJECTID | int | 51354 | 1; 2; 3 |
| DATASET_E | text | 51354 | Building information and age records |
| DATASET_C | text | 51354 | 樓宇資料及樓齡紀錄 |
| ADDRESS_E | text | 51354 | CHEUNG SHA DD 332 LOT 710 LANTAU ISLAND; DISCOVERY BAY NORTH DEVELOPMENT DISCOVERY BAY STT CX1333 LANTAU ISLAND; BLK A TUI MIN HOI CLP S4413 SAI KUNG |
| ADDRESS_C | text | 51354 | 大嶼山 長沙丈量約份第332約第710號地段; 大嶼山愉景灣第CX1333號短期租約; 對面海第S4413號官地租用許可證 A |
| SEARCH1_E | text | 51354 | Islands; Sai Kung; Tuen Mun |
| SEARCH1_C | text | 51354 | 離島區; 西貢; 屯門 |
| SEARCH2_E | text | 51354 | New Territories; Kowloon; Hong Kong |
| SEARCH2_C | text | 51354 | 新界; 九龍; 香港島 |
| NSEARCH1_E | int | 51354 | 5216949; 5216950; 5240508 |
| NSEARCH1_C | int | 51354 | 5216949; 5216950; 5240508 |
| NSEARCH2_E | text | 51354 | NT47/84; HD19/2000(OP); NT53/66 |
| NSEARCH2_C | text | 51354 | NT47/84; HD19/2000(OP); NT53/66 |
| NSEARCH3_E | text | 50575 | 1984-05-03; 2000-04-14; 1966-06-03 |
| NSEARCH3_C | text | 50575 | 1984-05-03; 2000-04-14; 1966-06-03 |
| NSEARCH4_E | text | 51354 | Tower; Podium |
| NSEARCH4_C | text | 51354 | 座; 平台 |
| NSEARCH5_E | text | 51354 | Residential/Composite; Others; Office/Commercial |
| NSEARCH5_C | text | 51354 | 住宅/綜合用途; 其他; 寫字樓/商業 |
| LATITUDE | float | 51354 | 22.23623065; 22.23613071; 22.31056115 |
| LONGITUDE | float | 51354 | 113.961824; 113.9617702; 113.9991111 |
| GeometryLongitude | float | 51354 | 113.96182400017756; 113.96177020003472; 113.99911109999732 |
| GeometryLatitude | float | 51354 | 22.236230649824677; 22.236130709964357; 22.310561150276897 |

## Gaps
- gpkg: licence / documentation not found in the folder
- bdbiar: licence / documentation not found in the folder
- No data dictionary for the HK-BFETD files was found next to them.