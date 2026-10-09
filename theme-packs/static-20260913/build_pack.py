import json
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path('/home/abigor/Workspace/Open-Trofeo-LCD')
sys.path.insert(0, str(ROOT))
from theme_schema import normalize_theme_document, ThemeDocument
from theme_renderer import render_theme_document
from preview_stats import PreviewStatsProvider, preview_stats_values
from PIL import Image

OUT = Path('/tmp/trofeo-static-pack-20260913')
OUT.mkdir(exist_ok=True)
orbital = json.loads((ROOT/'themes/orbital_relay.json').read_text())
gauge_base = next(x for x in json.loads((ROOT/'themes/valhalla_command.json').read_text())['stats'] if x.get('source') == 'gpu_load')

def base(name, accent, bg, panel):
    return dict(schema_version=1, meta=dict(name=name, author='Open Trofeo LCD', description='Static background with live Linux telemetry, music and weather.', tags=['static','starter-pack']), canvas=dict(width=1920,height=462,rotation=180), background=dict(kind='generated',base_color=bg,accent_color=panel,texture_alpha=0.04,panels=[]),texts=[],stats=[],images=[],widgets=[],effects=dict(animation=dict(enabled=False)))

def text(d, label, x,y,w,size=20,color=None):
    d['texts'].append(dict(id=f't{len(d["texts"])}',text=label,x=x,y=y,box_width=w,box_height=size+10,font_size=size,font_bold=True,color=color or [230,236,244,255]))

def stat(d,source,x,y,w=200,size=28,color=None):
    d['stats'].append(dict(id=f's{len(d["stats"])}',source=source,x=x,y=y,box_width=w,box_height=size+12,font_size=size,font_bold=True,value_color=color or [230,236,244,255]))

def panel(d,rect,color):
    d['background']['panels'].append(dict(rect=rect,radius=16,fill=color,opacity=1))

def widget(d,kind,rect,accent):
    w=deepcopy(next(x for x in orbital['widgets'] if x['kind']==kind))
    w['rect']=rect
    w['settings'].update(panel_fill=[0,0,0,0],panel_enabled=False,animate_icons=False,title_marquee=False,equalizer_color=accent,day_color=accent,backdrop_enabled=False)
    d['widgets'].append(w)

def gauge(d,source,label,x,y,accent):
    s=deepcopy(gauge_base)
    s.update(id=f'g{len(d["stats"])}',source=source,label=label,x=x,y=y,box_width=170,box_height=168,gauge_ring_size=125,font_size=30,fill_color=accent,value_color=accent,stroke_width=9)
    d['stats'].append(s)

amber=[244,186,95,255]
d=base('Amber Hi-Fi',amber,[14,12,10],[31,26,21])
text(d,'AMBER / HI-FI',30,18,600,28,amber)
text(d,'LISTEN  /  LIVE AUDIO & DESKTOP',31,55,650,13,[156,144,126,255])
stat(d,'time_hms',1670,20,210,30,amber)
panel(d,[24,91,1150,267],[29,24,19])
widget(d,'media_now_playing',[44,108,1110,227],amber)
d['widgets'][-1]['settings'].update(title_font_size=37,artist_font_size=25,equalizer_bars=42,detail_font_size=17)
panel(d,[1194,91,702,267],[25,25,24])
widget(d,'weather_current',[1215,112,660,210],amber)
for x,src,label in [(35,'cpu_usage_percent','CPU'),(325,'gpu_load','GPU'),(615,'mem_percent','RAM'),(905,'volume_percent','VOLUME'),(1250,'uptime_human','UPTIME')]:
    text(d,label,x,381,250,13,amber);stat(d,src,x,405,260,26)

themes={'amber_hi_fi':d}
ice=[129,211,206,255]
d=base('Nordic Forecast',ice,[10,21,28],[20,38,47])
text(d,'NORDIC / FORECAST',30,20,650,27,ice)
stat(d,'date_ymd',1100,22,310,24);stat(d,'time_hms',1650,14,240,37,ice)
panel(d,[24,78,584,276],[20,38,47]);widget(d,'weather_current',[44,119,544,182],ice)
d['widgets'][-1]['settings'].update(detail_font_size=12,location_font_size=16,temp_font_size=32)
panel(d,[626,78,1270,276],[16,31,41]);widget(d,'weather_forecast_7d',[648,124,1225,169],ice)
d['widgets'][-1]['settings'].update(day_font_size=17,temp_max_font_size=19,condition_font_size=12,location_font_size=18)
for x,src,label in [(35,'cpu_temp_c','CPU TEMP'),(355,'gpu_temp','GPU TEMP'),(675,'mem_percent','RAM'),(980,'net_dl_kbps','DOWNLOAD'),(1350,'volume_percent','VOLUME')]:
    text(d,label,x,377,300,13,ice);stat(d,src,x,405,300,27)
themes['nordic_forecast']=d

red=[255,104,109,255]
d=base('Crimson Telemetry',red,[16,10,17],[32,21,33])
text(d,'CRIMSON / TELEMETRY',30,18,560,27,red)
stat(d,'game_name',660,20,750,24);stat(d,'time_hms',1660,20,230,28)
panel(d,[24,76,550,359],[36,21,30]);text(d,'FRAME RATE',45,96,400,17,red)
stat(d,'game_fps',43,118,310,105);text(d,'FPS',356,170,150,35,red)
for x,src,label in [(48,'game_fps_min','MIN'),(220,'game_fps_avg','AVG'),(397,'game_fps_max','MAX')]:
    text(d,label,x,266,150,14,red);stat(d,src,x,292,155,32)
text(d,'FRAME TIME',46,369,190,14,red);stat(d,'game_frametime_ms',244,359,300,30)
panel(d,[594,76,760,359],[27,23,35])
for x,src,label in [(611,'gpu_load','GPU'),(795,'cpu_usage_percent','CPU'),(979,'mem_percent','RAM'),(1163,'vram_percent','VRAM')]:gauge(d,src,label,x,100,red)
for x,src,label in [(620,'gpu_temp','GPU TEMP'),(870,'cpu_temp_c','CPU TEMP'),(1120,'volume_percent','VOLUME')]:
    text(d,label,x,322,215,14,red);stat(d,src,x,355,220,30)
panel(d,[1374,76,522,359],[27,23,35]);text(d,'PROCESS MEMORY / RSS',1395,98,475,20,red)
for i in range(1,5):
    y=152+(i-1)*58
    stat(d,f'process_ram_{i}_name',1395,y,316,20)
    stat(d,f'process_ram_{i}_gib',1732,y,140,20,red)
text(d,'GiB / shared pages may be counted twice',1395,405,478,12,[155,145,160,255])
themes['crimson_telemetry']=d

for slug,d in themes.items():
    (OUT/f'{slug}.json').write_text(json.dumps(d,indent=2)+'\n')
    values=preview_stats_values()
    values['game_name']='DEMO / SYNTHETIC DATA'
    for i in range(1,5):
        values[f'process_ram_{i}_name']=f'demo-process-{i}'
        values[f'process_ram_{i}_gib']=str(round(3.6/i,2))
    preview=deepcopy(d)
    text(preview,'ILLUSTRATIVE PREVIEW / SYNTHETIC DATA',640,444,680,10,[160,170,185,255])
    doc=ThemeDocument(normalize_theme_document(preview))
    render_theme_document(doc,base_dir=ROOT/'themes',stats_provider=PreviewStatsProvider(values)).transpose(Image.Transpose.ROTATE_180).save(OUT/f'{slug}.png')
    print(slug)
