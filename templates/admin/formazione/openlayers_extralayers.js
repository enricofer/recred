{% extends "gis/admin/openlayers.js" %}
{% block extra_layers %}
    //prg_layer = new OpenLayers.Layer.WMS( "PI", "https://rapper.comune.padova.it/qgisserver?MAP=/usr/lib/cgi-bin/servizi/default.qgs", {layers: 'PI',transparent:"true",format:'image/png'},{ isBaseLayer: false}  );
    //{{ module }}.map.addLayer(prg_layer);
    dbt_layer = new OpenLayers.Layer.WMS( "DBT", "https://rapper.comune.padova.it/mapproxy?", {layers: 'DBT',format:'image/png'},{ isBaseLayer: true}  );
    {{ module }}.map.addLayer(dbt_layer);
    cat_layer = new OpenLayers.Layer.WMS( "CAT", "https://rapper.comune.padova.it/qgisserver?MAP=/usr/lib/cgi-bin/servizi/default.qgs", {layers: 'CATASTO',visibility:false,transparent:true,format:'image/png'},{ isBaseLayer: true} );
    {{ module }}.map.addLayer(cat_layer);
    orto_layer = new OpenLayers.Layer.WMS( "ORTO", "https://rapper.comune.padova.it/qgisserver?MAP=/usr/lib/cgi-bin/servizi/default.qgs", {layers: 'ORTO2007',format:'image/png'},{ isBaseLayer: true}  );
    {{ module }}.map.addLayer(orto_layer);
    vecchi_pdl_layer = new OpenLayers.Layer.WMS( "VECCHI PDL", "https://rapper.comune.padova.it/qgisserver?map=/usr/lib/cgi-bin/servizi/PUA/VECCHI_PDL.qgs", {layers: '0',visibility:false, format:'image/png'},{ isBaseLayer: true}  );
    {{ module }}.map.addLayer(vecchi_pdl_layer);
    cat_layer.setVisibility (false)
    OpenLayers.Feature.Vector.style.default.fillColor = 'blue';
    OpenLayers.Feature.Vector.style.default.fillOpacity = 0.25;
    OpenLayers.Feature.Vector.style.default.strokeWidth = 3;
    OpenLayers.Feature.Vector.style.default.strokeColor = "blue";
{% endblock extra_layers %}
