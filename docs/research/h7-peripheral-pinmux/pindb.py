"""Build ball -> pin -> {signal: AF} table for STM32H743IIKx (UFBGA176+25).

Inputs (downloaded from github.com/STMicroelectronics/STM32_open_pin_data, mcu/):
  STM32H743IIKx.xml                        pin list with ball positions and signal names
  IP/GPIO-STM32H747_gpio_v1_0_Modes.xml    AF numbers per pin and signal
  STM32H743IIKx symbol in the KiCad library (cross-check of ball <-> pin name)
Usage: python -I pindb.py <data_dir> <kicad_sym> <out_json>
"""
import json
import re
import sys
import xml.etree.ElementTree as ET

data, sym, out = sys.argv[1:4]
NS = '{http://dummy.com}'

mcu = ET.parse(f'{data}/STM32H743IIKx.xml').getroot()
gpio = ET.parse(f'{data}/GPIO-STM32H747_gpio_v1_0_Modes.xml').getroot()

af = {}
for p in gpio.iter(NS + 'GPIO_Pin'):
    d = {}
    for s in p.iter(NS + 'PinSignal'):
        v = s.find(f'{NS}SpecificParameter/{NS}PossibleValue').text  # GPIO_AF9_QUADSPI
        m = re.match(r'GPIO_AF(\d+)_', v)
        d[s.get('Name')] = int(m.group(1)) if m else v
    af[p.get('Name').split('-')[0].split(' ')[0]] = d   # 'PB3 (JTDO/TRACESWO)' -> 'PB3'

balls = {}
for p in mcu.iter(NS + 'Pin'):
    name = p.get('Name')
    sigs = [s.get('Name') for s in p.iter(NS + 'Signal')]
    key = name.split('-')[0].split(' ')[0]            # PC14-OSC32_IN -> PC14
    balls[p.get('Position')] = {
        'pin': name, 'type': p.get('Type'),
        'sig': {s: af.get(key, {}).get(s) for s in sigs if s != 'GPIO'},
    }

# cross-check with the KiCad symbol: ball number -> pin name
txt = open(sym, encoding='utf-8').read()
i = txt.index('(symbol "STM32H743IIKx"')
j = txt.index('\n\t(symbol "', i + 10)
blk = txt[i:j]
kc = {m.group(2): m.group(1) for m in re.finditer(
    r'\(name "([^"]*)".*?\)\s*\(number "([^"]+)"', blk, re.S)}
mism = [(b, balls[b]['pin'], kc.get(b)) for b in balls
        if kc.get(b) is None or
        kc[b].split('-')[0].split('/')[0] != balls[b]['pin'].split('-')[0].split(' ')[0]]
print('balls', len(balls), 'kicad pins', len(kc), 'name mismatches', len(mism))
for m in mism[:40]:
    print('  ', m)
json.dump(balls, open(out, 'w'), indent=0)
