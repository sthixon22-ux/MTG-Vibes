"""Regression: failed analysis must not hide the gallery or invent missing commanders."""
import json
import os
from playwright.sync_api import sync_playwright, expect
BASE=os.environ.get('MTG_TEST_URL','http://127.0.0.1:8029')
name="Eshki, Temur's Roar"
deck={'id':'eshki-failure','name':'Eshki','commander':name,'cards':[{'name':name,'quantity':1},{'name':'Forest','quantity':99}], 'commanderCheck':{'identity_verified':False,'issues':['Include '+name+' in the imported 100-card list.','Card data unavailable: Forest'],'unknown_cards':[name,'Forest'],'status':'issues'}}
with sync_playwright() as p:
 browser=p.chromium.launch()
 page=browser.new_page()
 page.add_init_script('localStorage.setItem("mtgvibes-library",JSON.stringify('+json.dumps([deck])+'));localStorage.setItem("mtgvibes-deck",JSON.stringify('+json.dumps(deck)+'));')
 page.route('**/api/deck-analysis',lambda r:r.fulfill(status=503,json={'error':'Scryfall card data could not be loaded.','code':'scryfall_unavailable','source_error':{'endpoint':'GET /cards/named','http_status':403}}))
 page.goto(BASE+'/analyze')
 expect(page.locator('.gallery-card')).to_have_count(2)
 expect(page.locator('#analysis-status')).to_contain_text('HTTP 403')
 expect(page.locator('#commander-check')).not_to_contain_text('Include '+name)
 expect(page.locator('#commander-check')).not_to_contain_text('Card data unavailable')
 assert page.evaluate('deck.cards.length')==2
 print('Failed metadata check preserves gallery, clears poisoned report, and displays actual source error.')
 browser.close()
