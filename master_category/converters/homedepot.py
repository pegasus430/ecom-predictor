import base64
import copy
import json
import os
import re
import time
import traceback
from StringIO import StringIO

import requests
import xlsxwriter
from requests.auth import HTTPBasicAuth
from xlsxwriter.utility import xl_col_to_name


class HomedepotTemplateGenerator(object):

    data_standard_api_url = 'http://tagglo.io/api/datastandards/v1/datastandards/home-depot/'
    client_id = 'CA_Stanley'
    api_key = 's23jk4h23jh'

    data_standard_file = '/tmp/ds.json'

    # base64 encoded vba bin file
    vba_project = '0M8R4KGxGuEAAAAAAAAAAAAAAAAAAAAAPgADAP7/CQAGAAAAAAAAAAAAAAABAAAAAQAAAAAAAAAAEAAAAgAAAAIAAAD+////AAAAAAAAAAD////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////9////DgAAABMAAAAEAAAABQAAAAYAAAAHAAAACAAAAAkAAAAKAAAACwAAAAwAAAANAAAADwAAAB0AAAAQAAAAEQAAABIAAAAUAAAA/v///xUAAAAWAAAAFwAAABgAAAAZAAAAGgAAABsAAAAcAAAAHgAAACUAAAAfAAAAIAAAACEAAAAiAAAAIwAAACQAAAD+/////v///////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////1IAbwBvAHQAIABFAG4AdAByAHkAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAWAAUA//////////8MAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAACCV7REqPdMBAwAAAMA9AAAAAAAAVgBCAEEAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAgAAQD//////////wQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABBu7REqPdMBIJXtESo90wEAAAAAAAAAAAAAAABUAGgAaQBzAFcAbwByAGsAYgBvAG8AawAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAGgACAQUAAAAHAAAA/////wAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAACMBAAAAAAAABsEOARBBEIEMQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAMAAIACAAAAAkAAAD/////AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAEwAAAGkPAAAAAAAAAQAAAAIAAAADAAAABAAAAAUAAAAGAAAABwAAAAgAAAAJAAAACgAAAAsAAAAMAAAADQAAAA4AAAAPAAAAEAAAABEAAAASAAAA/v///xQAAAAVAAAAFgAAABcAAAAYAAAAGQAAABoAAAAbAAAAHAAAAB0AAAAeAAAAHwAAACAAAAAhAAAAIgAAACMAAAAkAAAAJQAAACYAAAAnAAAAKAAAACkAAAAqAAAAKwAAACwAAAAtAAAALgAAAC8AAAAwAAAAMQAAADIAAAAzAAAANAAAADUAAAA2AAAANwAAADgAAAA5AAAAOgAAADsAAAA8AAAAPQAAAD4AAAA/AAAAQAAAAEEAAABCAAAAQwAAAEQAAABFAAAARgAAAEcAAABIAAAASQAAAEoAAABLAAAATAAAAE0AAABOAAAATwAAAFAAAAD+////UgAAAFMAAABUAAAAVQAAAFYAAABXAAAAWAAAAFkAAABaAAAAWwAAAFwAAABdAAAAXgAAAF8AAABgAAAAYQAAAGIAAABjAAAAZAAAAGUAAABmAAAAZwAAAGgAAABpAAAAagAAAGsAAABsAAAAbQAAAG4AAABvAAAAcAAAAHEAAAD+////cwAAAHQAAAD+////dgAAAHcAAAB4AAAAeQAAAHoAAAB7AAAAfAAAAH0AAAB+AAAAfwAAAIAAAAABFgMAAfQAAADmAgAA2AAAAAQCAAD/////7QIAAEEDAADTAwAAAAAAAAEAAABfDUr5AAD//yMBAACIAAAAtgD//wEBAAAAAP////8AAAAA////////AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAEAAAAAMAAAAFAAAABwAAAP//////////AQEIAAAA/////3gAAAAIAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD//wAAAABNRQAA////////AAAAAP//AAAAAP//AQEAAAAA3wD//wAAAAAYAP//////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////KAAAAAIAU0z/////AAABAFMQ/////wAAAQBTlP////8AAAAAAjz/////AAD//wEBAAAAAAEATgAwAHsAMAAwADAAMgAwADgAMQA5AC0AMAAwADAAMAAtADAAMAAwADAALQBDADAAMAAwAC0AMAAwADAAMAAwADAAMAAwADAAMAA0ADYAfQAGAAAAAAD/////AQFQAAAAAoD+//////8gAAAA/////zAAAAACAf//AAAAAAAAAAD//////////wAAMEV4Y2VsHQAAACUAAAD/////QAAAAP////84AAAA/////zAAAAAAAAAAAAABAAAAAAAAAAAA////////////////AAAAAP//////////////////////////AAAAAP//////////////////////////AAAAAAAAAAD//wAA////////AAAAAP///////////////////////////////wAAAQBAAAAAjjKpWxMA3wAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP7KAQAAAP////8BAQgAAAD/////eAAAAP////8BAQgAAAD/////eAAAAP///////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////wAAAa+wAEF0dHJpYnV0AGUgVkJfTmFtAGUgPSAiVGhpAHNXb3JrYm9viGsiCgqIQmFzAogAMHswMDAyMDioMTktABAwAwhDABSDAhIBJDAwNDZ9DHpAR2xvYmFsAcxTCHBhYwGQRmFscwJlC2JDcmVhdGEEYmwUHlByZWRlSGNsYQAGSWQArVQEcnUMQEV4cG9zAmUTG1RlbXBsYYB0ZURlcml2AiMBkUB1c3RvbWl6AwRCgjAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAARYDAAYEAQAALgYAAOgAAAA8AgAAqgYAALgGAAAMCwAAxgwAAAAAAAABAAAAXw037gAA//8jAQAAiAAAALYA//8BAQAAAAD/////AAAAAP//cAD//wAAQPnLAkjzTXKNNUqIgdqDViAIAgAAAAAAwAAAAAAAAEYAAAAAAAAAAAAAAAAAAAAAAQAAACXreSIysU4fu9cPZP5Rs9wQAAAAAwAAAAUAAAAHAAAA//////////8BAQgAAAD/////eAAAAAgl63kiMrFOH7vXD2T+UbPcQPnLAkjzTXKNNUqIgdqDVv//AAAAAE1FAAD///////8AAAAA//8AAAAA//8BAQAAAADfAP//AAAAAP//////////////////GAD///////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////9QAAAAAgBbTP////8AAAEAUxD/////AAABAFOU/////wAAAQA4TP//NgIAAAAANiL/////AAAAABoA/////wAAAAAaTP////8AAAAAGgj/////AAD//wEBAAAAAAEATgAwAHsAMAAwADAAMgAwADgAMgAwAC0AMAAwADAAMAAtADAAMAAwADAALQBDADAAMAAwAC0AMAAwADAAMAAwADAAMAAwADAAMAA0ADYAfQAHAAAAAAD/////AQFgAwAAAoD+//////8gAAAA/////zAAAAACAf//AAAAAAAAAAD//////////wAAaWgCAAAAHQAAACUAAAAMETIC/////wAAA2AAAAAA//////////8AAAAAAAAAAAAAAAAAAAAAYAEAADj///9rAAAAAAAAAIgAAAD/////SAQAACIAIgAAAJQBAAEAACmDNAL/////CAAAAP////+oAAAAAAAAAP////+EADctHQAYACUAAABghDgC//////D/////////CAD//wAAAABghDoC/////+j/////////CAD//wAAAAD/////GAAAAP////84AAAAAoP+//////8AAAAA/////yABAAAAAP///////wAAAAD//////////wAA////////HQAgACUAAACCoCwC//////7/////////WAEAAAIA///+////AAAAAP//////////AAD///////8dACAAJQAAAP////+wAAAA////////////////////////////////yAAAAP///////////////yACAAD/////////////////////KAMAAIACAADIAgAA/////5gCAAD/////UAIAAP//////////////////////////////////////////////////////////////////////////aAIAAEACAAAghDQC//////j/////////GAIAAIAAAAAdABgAJQAAACCENAL/////+P////////84AgAAgAAAAB0AGAAlAAAA/////yACAAAAAP//EAAAAEAE/v//////5P////////8DAP//IAAAAP////9SAkQCRgJMAtwATgJABP7/BgAAAEAE/v//////2P////////8JAP//IAAAAEAE/v+wAgAAwP////////8MAP//IAAAAEAE/v/gAgAAqP////////8MAP//IAAAAEAE/v/4AgAAkP////////8MAP//IAAAAEAE/v//////eP////////8MAP//IAAAAEAE/v8QAwAAYP////////8MAP//IAAAAEAE/v//////SP////////8MAP//IAAAAEAE/v9AAwAAQP////////8IAP//IAAAAEAE/v//////OP////////8IAP//IAAAAP////9AAAAAAQABAAAAAQAAAAAAAAAAADgAAAD//////////wAAAAD//////////zgAAAD//////////wAAAAD///////////////8oAQAA8AAAAAAAAAAAAAAAeAAAAAgAAAAAAFAESAT/////////////////////////////EAAAAAIA6AAAAI4yqVsTAAESACoAXABSADEAKgAjADEANAA3AAEkACoAXABSAGYAZgBmAGYAKgAwAGQANQBiAGEAOQAzADQAMgBjAAEQACoAXABSADEAKgAjADcANQABEgAqAFwAUgAxACoAIwAxADQANQABDgAqAFwAUgAwACoAIwBmAN8BAAAAAAD/////YAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP7KAQAiACKBDAAGABIAAAAAAACACAAIAAAACAAAAACACAAIAAAAEAAAAACBCAAEAAwAGAAAAACBCAAkAI4AIAAAAACBCAIUAEIASAAAAACBCAQEAAwAYAAAAACBCAIiAGIAaAAAAACBCAQKACgAkAAAAACBCAQMADoAoAAAAACBCAQKACwAsAAAAACBCAQMADoAwAAAAACBCAQMABgA0AAAAACBCAYMAC4A4AAAAACBCAQCAAwA8AAAAACBGAZUAIYA+AAAAACBCAgaAE4AUAEAAACBCAYGAAwAcAEAAACBCAgMABoAeAEAAACBCAoMACoAiAEAAACBCAgGAAwAmAEAAACBCAoYAEoAoAEAAACBCAwmAGAAuAEAAACBCAoCAAwA4AEAAACBCAwiAGgA6AEAAACBCAoCAAYAEAIAAACBCAgCAAYAGAIAAACBCAYCAAYAIAIAAACBCAQCAAYAKAIAAACBCAICAAYAMAIAAACBCAACAAYAOAIAAACACAAEAAAAQAIAAACBCAAKACoASAIAAASBCAACAAgAWAIAAP////8BAXACAACWBDgAAAAAAF0A9QSwAAAAXQD1BMgAAADMADwCAAAAAKwABgAgADQCIQBUAiQAUgICACEAQAK5AAUAbXVsdGkABQCcAAAAAAAgAEQCIAA0AiUAQgIBALIAFACcAAAAAACaADwCGAAAAGQARgAAACAANAIhAEACuQAAAAUAmwBHAJoAPAJjAEcAagAAAAAAAAC6ACAARgIoAEgCAAAAAAAAIAA0AiEAQAInADoCAAAAACAARgJCQEoCAAAAAAAAAAAgADQCIQBAAicAOAKAYAAAIAA4ArkAAAAFAJwAgGAAACAAOgIgADQCKABAAoBgAABkAP//CAAAAKYACAAOAAkAGwAJAKwAAQAgADgCuQACACwgIAA6AhEAhQCsAAAABQCsAAEAIAA4AiAAOgK5AAEALAARAIUArAAAAAUABAAgADgCIAA6AgYABACcAGkAcAAgADgCuQACACwgEQAgADoCEQAgADQCKABAAlIAZQBnAGQARgAAAAAAIAA4AiAAOgIFAJwAY2xhc7kAAAAgADQCKABAAi5vYmpkAEYAAAAAACAAOAIgADoCGwAkAEwCAgAgADoCBQCcACAAOAIgADgCGwAgADoCGwAMAKwAAgAMACQA3AACACAANAIoAEAC4BFkAP//GAAAACAAOAIgADoCuQACACwgEQC5AAAAJABOAgMAIAA0AigAQAIAAAAAAABrAP//6AEAAGsA///gAQAAawD//9gBAABrAP//0AEAAGsA///IAQAAawD//8ABAACjADwCuAEAALoEIABGAigASAIAAAAAAABvAP//oAEAAP////+YAQAA/////2ACAAD/////AQEwAQAA/////3gAAAAAAANgAAEAAP////8CAggCBgAAAAAAAAAAAAAAAwEAAAgAAAADAggCCGFyaWVzL2YBAAAAAwEAACAAAAACAggIAACMAYAAAAACAAAAAwEAADgAAAAFAggGBgIIAAAAAAADAAAAAwEAAFAAAAAFAggCBgII/wAAAAAEAAAAAwEAAP////8EAggGAggCEwEAAAAFAAAAAwEAAIAAAAACAggJKK44bNh/AAAGAAAAAwEAAJgAAAACAggCAwBhVv9/AAAHAAAAAwEAALAAAAAEAggGAgb//wAAAAAIAAAAAgEAAP////8DFAgIAgAAAAAAAAAJAAAAAgEAAOAAAAADFAgIApwAoACkAKgKAAAAAgEAAPgAAAAGBwcHBwICAgBEAEj/////0AAAAGgAAADIAAAAEAEAAP///////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////wAAAZmyAEF0dHJpYnV0AGUgVkJfTmFtAGUgPSAii+jxEPIxIgoK2EJhcwECbDB7MDAwMjCwODIwLQAgBBBDABSDAhwBJDAwNDZ9DHpAR2xvYmFsAb5TCHBhYwGQRmFscwJlC8RDcmVhdGEEYmwUHlByZWRlSGNsYQAGSWQAplQEcnUMQEV4cG9zAmUTG1RlbXBsYYB0ZURlcml2AiMBEYF1c3RvbWl6GwRCgjBQgBeAGyBTdQBiIFdvcmtzaABlZXRfQ2hhbgBnZShCeVZhbAAgVGFyZ2V0IBBBcyBSgQopCkQAaW0gT2xkdmEobHVlAQtTALJuZxECC05ldw0LT24gAEVycm9yIEdvAFRvIEV4aXRzAHViCklmIENlQGxscyg2LAQwLgBDb2x1bW4pLgeAOYArANRtdWx0aQAiIFRoZW4KIAYggBiDRC5TcGVjKGlhbIMfeIIDVHkgcGVBbGwAHWlkAGF0aW9uKSBJAHMgTm90aGluimdFECCLICAgRQBpfjoIFkYeAx2KCwILgCEggCBBcHBsaWNCGQguRW4BU0V2ZW5sdHMAbQNdIAAABkI9h4U3AhcOEFVuZG8CBe8GVBAMgD6IByKGRAEaxEQ/hS7FHcIUwTcCAkJPSW4RAGooMSzGbiwgIlGAACAmIAUNKYAwMMAgQW5kIF+EDUAYx5ANxQuADiIsIlINxiu8PD6GF8dhEC4GDCZNJf+EIgJrhiWLRAYkxIrBF9AYHCIi5gerCeIjUmlnCGh0KOUQLCBMZbRuKAULKYEctQwgSjwxYChMZWYNCcUKKSDmLQsL4AEyKcYSY1LIAcluC1JlAH1jZegUxhKbIydAOiIKCsA5SWZGCn5FyQGIAUYBBAHFAON1Oi4KuF4CieEFUwB7AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAByVfgBAAAAAAAAAAAAAAAAAABAAAAAAAAAAEAAAAAAAAAAAAAAAAAAAAA4AAAAAAAAABEAAAAAAAAAAAAAABEAAAAAAAAAAAADAFAAAAAAAAAAAAAAAAEAAQAQAAAAgQgAAAAAAAAAAAAAoQkAAAAAAAAAAAAAwQoAAAAAAAAAAAAAsQwAAAAAAAAAAAAAIQ4AAAAAAAAAAAAA0Q8AAAAAAAAAAAAA8RAAAAAAAAAAAAAAERIAAAAAAAAAAAAA4RMAAAAAAAAAAAAAcRUAAAAAAAAAAAAAARcAAAAAAAAAAAAAUQwAAAAAAAAAAAAAgQwAAAAAAAAAAAAAgQ8AAAAAAAAAAAAAkRMAAAAAAAAAAAAAwRMAAAAAAAAAAAAAAQABAAAAAQDhBgAAAAAAAAAAAAARBwAAAAAAAAAAAABBBwAAAAAAAAAAAAD//////////7EGAAAAAAAAAAAAAAgADgBgAAAAcQcAAAAAAAAAAAAAsQAAAAAAAAAAAAEAoQcAAAAAAAAAAAAA////////////////AQAJBgAAAAADYAkEAAAAAAAAAAACAP//////////////////////////XwBfAFMAUgBQAF8AMgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABAAAgEDAAAAAgAAAP////8AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABRAAAAOAgAAAAAAABfAF8AUwBSAFAAXwAzAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAEAACAP///////////////wAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAHIAAAC2AAAAAAAAABsEOARBBEIEMgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAMAAIA////////////////AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAdQAAAIMEAAAAAAAAXwBWAEIAQQBfAFAAUgBPAEoARQBDAFQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABoAAgD///////////////8AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAACIAAAAIw0AAAAAAAD/////////////////////////////////////////////////////////////////////////////////////////////////////////////////////AQCCAMkCAAAAAAAAAAACAK4FAAAAAAAAHAUAAAAAAABnAhIAAACYAggAAAC4Avj///9nAgwAAADOAugEAABnAo4AAACfAuT///+QBQkEAACeAvj////yASABAACfApD///+QBQkEAACSAuT///9sA6j///8ZApgFwP///wYAGQKfAtj////BA/IBoAEBAJ4C2P////IBmAECAJ8CkP///zkGYP///wsAngV4////DADFAksAvgPY////igUEAJD///9g////xwLiBAAAZwJCAAAAnwLY////kAUJBAAA8QHA////GQKQBbLv//+eAvj////yARAFAwCYAtj////sASYBvgPY////xwIAAQAAZwIMAAAAxgLoBAAAxgLcBAAAZwIGAAAAZwJEAAAAnwKQ////kAUJBAAA8QHA////GQKeAvj////yAYgFBACWApD///+eBaj///8NAMUCSwC8A5D////HAlwBAABnAgwAAADGAugEAADGAlwBAABnAigAAAASBp8C2P///8ED8gE4AAEAngLY////8gFgCQUAvgPY////ZwI6AAAAnwKQ////kAUJBAAA8QHA////GQKeAvj////yAYgFBACWApD///9gBLcC6P///7wDkP///2cCLAAAAJAFCQQAAJ8C2P///8ED8gE4AAEAngLY////8gF4CAYAvgPY////ZwI6AAAAnwKQ////kAUJBAAA8QHA////GQKeAvj////yAYgFBACWApD///9gBLcC8P///7wDkP///2cCGAAAAJcC8P///5cFDQBEAMcCcAIAAGcCLgAAAJcC6P///3EDqP///xkCkAUJBAAA8QHA////GQKeAvj////yAZAFBwDGAtYEAABnAgYAAABnAoYAAACQBQEAAACXAvD///+XBQ4AlwLo////UAFnA0D///+QBQAAAADwBZAFAAAAAD8AkAUBAAAAlwLw////lwLo////lwUPAFABZwM4////kAUAAAAA8AWQBQAAAAA/ADIAlwLw////lwLo////VQAyAIsFBABA////OP///8cCUAMAAGcCTgAAAJcC8P///5cFDgBQAWcDQP///5cC6P///1ABcQOQ////GQKQBQkEAADxAcD///8ZAp4C+P////IBkAUHAL0DQP///7wDkP///8YC0AQAAGcCBgAAAGcCGgAAAJcC8P///5cC6P///0QAxwKgAwAAZwIqAAAAngWo////DQAZApAFCQQAAPEBwP///xkCngL4////8gGQBQcAxgLKBAAAZwIGAAAAZwJKAAAAlwLo////TAGfAvD///+3A8D///8IQJ8CkP///78ECAAYAJYCkP///5cC6P///3EDqP///8UCSwC8A5D////HAlYEAABnAmAAAACXAvD///9MAZcC6P///0wB0ACQBQIAAADQAJ8C8P///7cDwP///whAnwKQ////vwQJABgAoAKQ////kAUJBAAA8QGo////GQKeAvj////yAZAFBwC8A5D////GAsQEAABnAgYAAABnAmgAAACQBQAAAACQBf////+QBQEAAACXBQ0AlwLo////lwUOAFABZwNA////lwLw////twQKADAAcQOQ////GQKQBQkEAADxAcD///8ZAp4C+P////IBkAUHAL0DQP///7wDkP///2cCBgAAAGcCBgAAAGcCBgAAAGcCBgAAAGcCBgAAAGcCBgAAAGcCKgAAAI0F//+fAtj////BA/IBOAABAJ4C2P////IBYAkFAL4D2P///2cCAAAAAPYBAAAAAAAAAAAAABAAyAAcBQAAUAAAAAgAAAAAAAAAAAAAAAAAAAAqAAAAAAAAAAAAAwAAAAAAAAAAAPD///8BAAAA6P///wEACmz4////AwAKbEIAAAAAAAAAAAAGAAAAAAAAAAAAQP///wEAAAA4////AQAAANj///8DACMAkP///wIA//9g////AgACAUj///8CABQAAAAAAAATAABgAJECAAAAAAAAAAACANEDAAAAAAAAAAACACYAAAAAAAAOAAJ5AAIIAiYAAAAAAAAOAAJ5AAIIAk4DAAAAAAB/AAAAAAAAAAAAAAAAAAAAAHJV+AEAAAAAAAAAAAAAAAAAAEAAAAAAAAAAQAAAAAAAAAAAAAAAAAAAABoAAAAAAAAAEQAAAAAAAAAAAAIA////////////////AAAAAHgAAAAIAEgA4QEAAAAAAAAAAAIAAAADYAQASAQ4AP////////////////////8AAAAAMQEAAAAAAAAAAAEAAAAAAB8AHgDxAAAAAAAAAAAAAQAAAAAAAADSAwAAAAAAfwAAAAAAAAAAAAAAAAAAAAAAAAEWAwAB9AAAAOYCAADYAAAABAIAAP/////tAgAAQQMAANMDAAAAAAAAAQAAAF8NvBoAAP//IwEAAIgAAAC2AP//AQEAAAAA/////wAAAAD///////8AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAQAAAAAwAAAAUAAAAHAAAA//////////8BAQgAAAD/////eAAAAAgAAAAAAAAAAAAAAAAAAIEAAACCAAAAgwAAAIQAAACFAAAAhgAAAIcAAAD+////iQAAAIoAAACLAAAAjAAAAI0AAACOAAAAjwAAAJAAAACRAAAAkgAAAJMAAACUAAAAlQAAAJYAAACXAAAAmAAAAJkAAACaAAAAmwAAAJwAAACdAAAAngAAAJ8AAACgAAAAoQAAAKIAAACjAAAApAAAAKUAAACmAAAApwAAAKgAAACpAAAAqgAAAKsAAACsAAAArQAAAK4AAACvAAAAsAAAALEAAACyAAAAswAAALQAAAC1AAAAtgAAALcAAAC4AAAAuQAAALoAAAC7AAAAvAAAAP7///++AAAAvwAAAMAAAADBAAAAwgAAAMMAAADEAAAAxQAAAMYAAADHAAAA/v///8kAAADKAAAAywAAAMwAAADNAAAAzgAAAM8AAADQAAAA0QAAANIAAADTAAAA1AAAANUAAADWAAAA1wAAANgAAADZAAAA2gAAANsAAADcAAAA3QAAAN4AAADfAAAA4AAAAOEAAADiAAAA4wAAAOQAAADlAAAA5gAAAOcAAADoAAAA6QAAAP7////rAAAA7AAAAO0AAADuAAAA/v////AAAAD+////8gAAAPMAAAD0AAAA9QAAAPYAAAD+////////////////////////////////////////////////////AAAAAAAAAAAAAAAAAAAAAAAA//8AAAAATUUAAP///////wAAAAD//wAAAAD//wEBAAAAAN8A//8AAAAAGAD//////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////ygAAAACAFNM/////wAAAQBTEP////8AAAEAU5T/////AAAAAAI8/////wAA//8BAQAAAAABAE4AMAB7ADAAMAAwADIAMAA4ADIAMAAtADAAMAAwADAALQAwADAAMAAwAC0AQwAwADAAMAAtADAAMAAwADAAMAAwADAAMAAwADAANAA2AH0ABgAAAAAA/////wEBUAAAAAKA/v//////IAAAAP////8wAAAAAgH//wAAAAAAAAAA//////////8AAGloAgAAAB0AAAAlAAAA/////0AAAAD/////OAAAAP////8wAAAAAAAAAAAAAQAAAAAAAAAAAP///////////////wAAAAD//////////////////////////wAAAAD//////////////////////////wAAAAAAAAAA//8AAP///////wAAAAD///////////////////////////////8AAAEAQAAAAI4yqVsTAN8AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD+ygEAAAD/////AQEIAAAA/////3gAAAD/////AQEIAAAA/////3gAAAD///////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////8AAAGmsABBdHRyaWJ1dABlIFZCX05hbQBlID0gIovo8RDyMiIKCthCYXMBAmwwezAwMDIwsDgyMC0AIAQQQwAUgwIcASQwMDQ2fQx6QEdsb2JhbAG+UwhwYWMBkEZhbHMCZQvEQ3JlYXRhBGJsFB5QcmVkZUhjbGEABklkAKZUBHJ1DEBFeHBvcwJlExtUZW1wbGGAdGVEZXJpdgIjARGBdXN0b21pegMEQoIwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAMxh2QAAAwD/GQQAAAkEAAAXJwMAAAAAAAAAAAABAAQAAgBOASoAXABIAHsAMAAwADAAMgAwADQARQBGAC0AMAAwADAAMAAtADAAMAAwADAALQBDADAAMAAwAC0AMAAwADAAMAAwADAAMAAwADAAMAA0ADYAfQAjADYALgAwACMAOQAjAC8AQQBwAHAAbABpAGMAYQB0AGkAbwBuAHMALwBNAGkAYwByAG8AcwBvAGYAdAAgAEUAeABjAGUAbAAuAGEAcABwAC8AQwBvAG4AdABlAG4AdABzAC8AUwBoAGEAcgBlAGQAUwB1AHAAcABvAHIAdAAvAFQAeQBwAGUAIABMAGkAYgByAGEAcgBpAGUAcwAvADYANAAtAGIAaQB0AC8AVgBiAGUARQBOADYALgB0AGwAYgAjAFYAaQBzAHUAYQBsACAAQgBhAHMAaQBjACAARgBvAHIAIABBAHAAcABsAGkAYwBhAHQAaQBvAG4AcwAAAAAAAAAAAAAAAABeASoAXABIAHsAMAAwADAAMgAwADgAMQAzAC0AMAAwADAAMAAtADAAMAAwADAALQBDADAAMAAwAC0AMAAwADAAMAAwADAAMAAwADAAMAA0ADYAfQAjAGUALgAwACMAMAAjAC8AQQBwAHAAbABpAGMAYQB0AGkAbwBuAHMALwBNAGkAYwByAG8AcwBvAGYAdAAgAEUAeABjAGUAbAAuAGEAcABwAC8AQwBvAG4AdABlAG4AdABzAC8AUwBoAGEAcgBlAGQAUwB1AHAAcABvAHIAdAAvAFQAeQBwAGUAIABMAGkAYgByAGEAcgBpAGUAcwAvAE0AaQBjAHIAbwBzAG8AZgB0ACAARQB4AGMAZQBsAC4AdABsAGIAIwBNAGkAYwByAG8AcwBvAGYAdAAgAEUAeABjAGUAbAAgADEANAAuADAAIABPAGIAagBlAGMAdAAgAEwAaQBiAHIAYQByAHkAAAAAAAAAAAAAAAAAtgAqAFwASAB7ADAARAA0ADUAMgBFAEUAMQAtAEUAMAA4AEYALQAxADAAMQBBAC0AOAA1ADIARQAtADAAMgA2ADAAOABDADQARAAwAEIAQgA0AH0AIwAyAC4AMAAjADAAIwBmAG0AMgAwAC4AdABsAGIAIwBNAGkAYwByAG8AcwBvAGYAdAAgAEYAbwByAG0AcwAgADIALgAwACAATwBiAGoAZQBjAHQAIABMAGkAYgByAGEAcgB5AAAAAAAAAAAAAAABAFgBKgBcAEgAewBFADQARAAxADUAOABGAEIALQBDADcAMAAxAC0ANgBDADQAMwAtADgARQA4ADIALQA2ADIARgA1AEUAQQA2ADQAMQAxAEEAMQB9ACMAMgAuADAAIwAwACMALwBVAHMAZQByAHMALwBBAG4AZAByAGUAeQAvAEwAaQBiAHIAYQByAHkALwBDAG8AbgB0AGEAaQBuAGUAcgBzAC8AYwBvAG0ALgBtAGkAYwByAG8AcwBvAGYAdAAuAEUAeABjAGUAbAAvAEQAYQB0AGEALwBMAGkAYgByAGEAcgB5AC8AUAByAGUAZgBlAHIAZQBuAGMAZQBzAC8ATQBTAEYAbwByAG0AcwAuAGUAeABkACMATQBpAGMAcgBvAHMAbwBmAHQAIABGAG8AcgBtAHMAIAAyAC4AMAAgAE8AYgBqAGUAYwB0ACAATABpAGIAcgBhAHIAeQAAAAAAAAAAAAAAAQAAAOEuRQ2P4BoQhS4CYIxNC7QAANAAKgBcAEgAewAyAEQARgA4AEQAMAA0AEMALQA1AEIARgBBAC0AMQAwADEAQgAtAEIARABFADUALQAwADAAQQBBADAAMAA0ADQARABFADUAMgB9ACMAMgAuADAAIwAwACMATQBpAGMAcgBvAHMAbwBmAHQATwBmAGYAaQBjAGUALgB0AGwAYgAjAE0AaQBjAHIAbwBzAG8AZgB0ACAATwBmAGYAaQBjAGUAIAAxADQALgAwACAATwBiAGoAZQBjAHQAIABMAGkAYgByAGEAcgB5AAAAAAAAAAAAAAAAAAMAAgACAAIABwASAgAAFAIAABYCAQAYAgEAGgIBABwCAQAeAg8AJAL///////8AAAAAAAAAAI4yqVsTAP////////////8AAP//AgD/////////////////////////////////////////////////////AQD///////8BAAAAAAAAAAAAAAAAAAAAAAAAAF8NAwAYAFQAaABpAHMAVwBvAHIAawBiAG8AbwBrABQAMABhADUAYgBhADkAMwAyADgAZQD//ykCGABUAGgAaQBzAFcAbwByAGsAYgBvAG8AawD//0r5AAAAAAAAAAIAAADZAwAA//8KABsEOARBBEIEMQAUADAAZAA1AGIAYQA5ADMANAAyAGMA//8tAgoAGwQ4BEEEQgQxAP//N+4AAAAAAAAYAgAAAMwMAAD//woAGwQ4BEEEQgQyABQAMABjADUAYgBhADkAMwAyADgAZQD//y8CCgAbBDgEQQRCBDIA//+8GgAAAAAAADACAAAA2QMAAP///////wEBUAIAAP//////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////AAIAAP//////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////MAIAAP//////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////GAIAAP//////////////////////////ODdVHeadT2O/4JXMqwT7vP////8BAAAAbdQAuKZrS2K7a784rKFSOv////8BAAAAGGdLzsXJRtOZl8F3FzfDff////8BAAAA/////zAAAACAAAAAAAAvASkABgFYMAAABQxFeGNlbIArMAADDFZCQffiMAAFBFdpbjE2jxAwAAUEV2luMzLVEDAABQRXaW42NEYRMAADBE1hY7OyMAAEBFZCQTatIzAABARW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AA4DAmEAAgjIsQYAAAAAAAAAAAAAMAAAAAAAAA4DBZYAAggGBgLIEQgAAAAAAAAAAAAABAAAAAAAAAEKAAAAAAAAAFYAYQBsAHUAZQAEAAAAAAAACwoAAABtAHUAbAB0AGkALAAAAAAAAA4DBYIAAggCBgLIEQgAAAAAAAAAAAAAKgAAAAAAAA4DBH8AAggGAsgRCAAAAAAAAAAAAAACAAAAAAAACwAAAAAEAAAAAAAAA9UIAgAAAAAAwAAAAAAAAEYiAAAAAAAADgMCYQACCAmhDwAAAAAAAAAAAAAiAAAAAAAADgMCYQACCAKhDwAAAAAAAAAAAAAuAAAAAAAADgMEjwACCAYCBhEIAAAAAAAAAAAAAAQAAAAAAAALBAAAACwAIAACAAAAAAAACwIAAAAsAA4AAAAAAAAH/////////////////////2sCCwBhFAAAAAAAAAAAAABQAQAAAAAAAAAAAAAgAAAAAAAADgIDZAAUyAgCDgAAAAAAAAf/////////////////////aQILAPEVAAAAAAAAAAAAAJABAAAAAAAAAAAAACAAAAAAAAAOAgNkABTICAIOAAAAAAAAB//////////////////////IAgsAgRcAAAAAAAAAAAAA0AEAAAAAAAAAAAAAJgAAAAAAAA4CBnUABwcHBwICAtgAAAAAAAB/AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAByVfgBAAAAAAAAQAAAAAAAAABAAAAAAAAAAEAAAAAAAAAAAgAAAAAAAH4CAAAAAAAAfnYAAAAAAAB/AAAAAAAAAAASAAAAAAAAABEAAAAAAAAAAAAAAP//////////////////////////AAAAAP//////////EQAAAAAAAAAAAAMA//////////8GAAAAAAAACWEDAAAAAAAAAAAAAHEHAAAAAAAAAAAAABAAAAAAAAAAAAABAAYAAAAAAAAJYQMAAAAAAAAAAAAAEQgAAAAAAAAAAAAAMAAAAAAAAAAAAAEAAgAAAAAAAAgGAAAAAAAAAFRhcmdldMYDAAAAAAB/AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAFRoaXNXb3JrYm9vawBUAGgAaQBzAFcAbwByAGsAYgBvAG8AawAAAIvo8fIxABsEOARBBEIEMQAAAIvo8fIyABsEOARBBEIEMgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAASUQ9IntCMjdCNzY4Ri0xNjdGLUQ4NDQtODg1Qi0wOTcxRDA1NkFFNzF9Ig0KRG9jdW1lbnQ9VGhpc1dvcmtib29rLyZIMDAwMDAwMDANCkRvY3VtZW50PYvo8fIxLyZIMDAwMDAwMDANCkRvY3VtZW50PYvo8fIyLyZIMDAwMDAwMDANCk5hbWU9IlZCQVByb2plY3QiDQpIZWxwQ29udGV4dElEPSIwIg0KQ01HPSJDOENBMTk5RjFEOUYxRDlGMUQ5RjFEIg0KRFBCPSI2RTZDQkY5QkMzRTc2OEU4NjhFODY4Ig0KR0M9IjE0MTZDNTQxQ0RFNkNFRTZDRTE5Ig0KDQpbSG9zdCBFeHRlbmRlciBJbmZvXQ0KJkgwMDAwMDAwMT17MzgzMkQ2NDAtQ0Y5MC0xMUNGLThFNDMtMDBBMEM5MTEwMDVBfTtWQkU7JkgwMDAwMDAwMA0KAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAFAAUgBPAEoARQBDAFQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAQAAIBAQAAAAsAAAD/////AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA8QAAAFwBAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD///////////////8AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP///////////////wAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////////////////AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'

    def generate(self, category_id, data_standard=None):
        if not data_standard:
            data_standard = self._get_data_standard()

        category = self._get_category(data_standard, category_id)

        if not category:
            raise Exception('Category with id {} does not exist'.format(category_id))

        attributes = self._get_attributes(data_standard, category_id)

        content = StringIO()

        with xlsxwriter.Workbook(content) as workbook:
            workbook.add_vba_project(StringIO(base64.b64decode(self.vba_project)), is_stream=True)
            workbook.set_vba_name('Workbook')

            sheet = workbook.add_worksheet('Attributes')
            sheet.set_vba_name('Attributes')

            values = workbook.add_worksheet('Values')
            values.set_vba_name('Values')
            values.hide()

            header = ['Attribute ID', 'Attribute Name', 'Attribute Type', 'Attribute Description', 'Attribute Fields']
            header_format = workbook.add_format({'bold': True,
                                                 'align': 'center',
                                                 'valign': 'vcenter',
                                                 'fg_color': '#D7E4BC',
                                                 'border': 1})

            sheet.write_column(0, 0, header)
            sheet.set_column(0, 0, 20, header_format)
            sheet.freeze_panes(5, 1)

            general_format = workbook.add_format({'align': 'center'})
            description_format = workbook.add_format({'text_wrap': True, 'align': 'center'})
            date_format = workbook.add_format({'num_format': 'yyyy-mm-dd'})
            integer_format = workbook.add_format({'num_format': '0'})
            decimal_format = workbook.add_format({'num_format': '0.####'})
            string_format = workbook.add_format({'num_format': '@'})
            url_format = workbook.add_format({'color': 'blue', 'underline': 1, 'num_format': '@'})

            sheet.set_row(5, None, None, {'hidden': True})

            column = 1

            for attribute in attributes:
                attribute_type = 'Optional' if attribute['optional'] else 'Required'

                units = attribute['type']['units']
                if units:
                    sheet.set_column(column, column, 20)

                    sheet.merge_range(0, column, 0, column + 1, attribute['id'], header_format)
                    sheet.merge_range(1, column, 1, column + 1, attribute['name'], general_format)
                    sheet.merge_range(2, column, 2, column + 1, attribute_type, general_format)
                    sheet.merge_range(3, column, 3, column + 1, attribute['description'], description_format)
                    sheet.write(4, column, 'Attribute Value', general_format)
                    sheet.write(4, column + 1, 'Attribute Units', general_format)

                    sheet.set_column(column + 1, column + 1, 20, string_format)
                    sheet.data_validation(6, column + 1, sheet.xls_rowmax - 1, column + 1, {
                        'validate': 'list',
                        'source': units,
                        'ignore_blank': False,
                        'input_title': 'Select units:',
                        'input_message': 'from list'})
                else:
                    sheet.set_column(column, column, 40)

                    sheet.write(0, column, attribute['id'], header_format)
                    sheet.write(1, column, attribute['name'], general_format)
                    sheet.write(2, column, attribute_type, general_format)
                    sheet.write(3, column, attribute['description'], description_format)
                    sheet.write(4, column, 'Attribute Value', general_format)

                list_of_values = attribute['listOfValuesFilter'] or attribute['type']['restriction']['listOfValues']
                if list_of_values:
                    values.write_column(0, column, list_of_values)

                    source = '={sheet}!${column}$1:${column}${row}'.format(
                        sheet='Values',
                        column=xl_col_to_name(column),
                        row=len(list_of_values)
                    )

                    attribute_format = {
                        'validate': 'list',
                        'source': source,
                        'input_message': 'from list'
                    }

                    if attribute['type']['multiValue']:
                        sheet.write(5, column, 'multi')
                        attribute_format['input_title'] = 'Select values:'
                    else:
                        attribute_format['input_title'] = 'Select value:'

                    sheet.data_validation(6, column, sheet.xls_rowmax - 1, column, attribute_format)
                elif attribute['type']['id'] == 'asset':
                    sheet.set_column(column, column, 20 if units else 40, url_format)

                    attribute_format = {
                        'validate': 'any',
                        'input_title': 'Enter an URL with content type:', 'input_message': 'any'
                    }

                    content_types = attribute['type']['restriction']['parameters'].get('contentTypes')

                    if content_types:
                        content_types = json.loads(content_types)

                        attribute_format['input_message'] = ', '.join(content_types)

                    sheet.data_validation(6, column, sheet.xls_rowmax - 1, column, attribute_format)
                elif attribute['type']['id'] == 'string':
                    sheet.set_column(column, column, 20 if units else 40, string_format)

                    attribute_format = {
                        'validate': 'any',
                        'input_title': 'Enter a string:',
                        'input_message': 'any'
                    }

                    min_length = attribute['type']['restriction']['parameters'].get('minLength')
                    max_length = attribute['type']['restriction']['parameters'].get('maxLength')

                    if min_length or max_length:
                        attribute_format['validate'] = 'length'

                        if min_length and not max_length:
                            attribute_format['criteria'] = '>='
                            attribute_format['value'] = int(min_length)
                            attribute_format['input_message'] = 'length greater than {}'.format(min_length)
                        elif not min_length and max_length:
                            attribute_format['criteria'] = '<='
                            attribute_format['value'] = int(max_length)
                            attribute_format['input_message'] = 'length less than {}'.format(max_length)
                        else:
                            attribute_format['criteria'] = 'between'
                            attribute_format['minimum'] = int(min_length)
                            attribute_format['maximum'] = int(max_length)
                            attribute_format['input_message'] = 'length between {} and {}'.format(min_length, max_length)

                    patterns = attribute['type']['restriction']['patterns']
                    if patterns:
                        attribute_format['input_message'] += '. ' + patterns[0].get('message')

                    sheet.data_validation(6, column, sheet.xls_rowmax - 1, column, attribute_format)
                elif attribute['type']['id'] == 'decimal':
                    sheet.set_column(column, column, 20 if units else 40, decimal_format)

                    attribute_format = {
                        'validate': 'any',
                        'input_title': 'Enter a decimal:',
                        'input_message': 'any'
                    }

                    min_value = attribute['type']['restriction']['parameters'].get('minValue')
                    max_value = attribute['type']['restriction']['parameters'].get('maxValue')

                    if min_value or max_value:
                        attribute_format['validate'] = 'decimal'

                        if min_value and not max_value:
                            attribute_format['criteria'] = '>='
                            attribute_format['value'] = float(min_value)
                            attribute_format['input_message'] = 'greater than {}'.format(min_value)
                        elif not min_value and max_value:
                            attribute_format['criteria'] = '<='
                            attribute_format['value'] = float(max_value)
                            attribute_format['input_message'] = 'less than {}'.format(max_value)
                        else:
                            attribute_format['criteria'] = 'between'
                            attribute_format['minimum'] = float(min_value)
                            attribute_format['maximum'] = float(max_value)
                            attribute_format['input_message'] = 'between {} and {}'.format(min_value, max_value)

                    patterns = attribute['type']['restriction']['patterns']
                    if patterns:
                        attribute_format['input_message'] += '. ' + patterns[0].get('message')

                    sheet.data_validation(6, column, sheet.xls_rowmax - 1, column, attribute_format)
                elif attribute['type']['id'] == 'integer':
                    sheet.set_column(column, column, 20 if units else 40, integer_format)

                    attribute_format = {
                        'validate': 'any',
                        'input_title': 'Enter an integer:',
                        'input_message': 'any'
                    }

                    min_value = attribute['type']['restriction']['parameters'].get('minValue')
                    max_value = attribute['type']['restriction']['parameters'].get('maxValue')

                    if min_value or max_value:
                        attribute_format['validate'] = 'integer'

                        if min_value and not max_value:
                            attribute_format['criteria'] = '>='
                            attribute_format['value'] = int(min_value)
                            attribute_format['input_message'] = 'greater than {}'.format(min_value)
                        elif not min_value and max_value:
                            attribute_format['criteria'] = '<='
                            attribute_format['value'] = int(max_value)
                            attribute_format['input_message'] = 'less than {}'.format(max_value)
                        else:
                            attribute_format['criteria'] = 'between'
                            attribute_format['minimum'] = int(min_value)
                            attribute_format['maximum'] = int(max_value)
                            attribute_format['input_message'] = 'between {} and {}'.format(min_value, max_value)

                    patterns = attribute['type']['restriction']['patterns']
                    if patterns:
                        attribute_format['input_message'] += '. ' + patterns[0].get('message')

                    sheet.data_validation(6, column, sheet.xls_rowmax - 1, column, attribute_format)
                elif attribute['type']['id'] == 'gtin':
                    sheet.set_column(column, column, 20 if units else 40, integer_format)

                    attribute_format = {
                        'validate': 'any',
                        'input_title': 'Enter a GTIN:',
                        'input_message': 'any'
                    }

                    gtin_sizes = attribute['type']['restriction']['parameters'].get('gtinSizes')

                    if gtin_sizes:
                        attribute_format['validate'] = 'length'

                        gtin_sizes = json.loads(gtin_sizes)

                        min_length = gtin_sizes[0]
                        max_length = gtin_sizes[-1]

                        if min_length == max_length:
                            attribute_format['criteria'] = '='
                            attribute_format['value'] = int(min_length)
                            attribute_format['input_message'] = 'length equal to {}'.format(min_length)
                        else:
                            attribute_format['criteria'] = 'between'
                            attribute_format['minimum'] = int(min_length)
                            attribute_format['maximum'] = int(max_length)
                            attribute_format['input_message'] = 'length between {} and {}'.format(min_length,
                                                                                                  max_length)

                    sheet.data_validation(6, column, sheet.xls_rowmax, column, attribute_format)
                elif attribute['type']['id'] == 'date':
                    sheet.set_column(column, column, 20 if units else 40, date_format)

                    attribute_format = {
                        'validate': 'any',
                        'input_title': 'Enter a date:',
                        'input_message': 'YYYY-MM-DD'
                    }

                    sheet.data_validation(6, column, sheet.xls_rowmax, column, attribute_format)
                else:
                    sheet.set_column(column, column, 20 if units else 40, string_format)

                column += 2 if units else 1

        content.seek(0)

        return {
            'content': content,
            'name': u'{}_{}.xlsm'.format(re.sub(r'/', ' ',
                                                '_'.join(self._get_categories_path(data_standard, category_id))),
                                         category_id)
        }

    def _get_data_standard(self):
        if os.path.exists(self.data_standard_file) \
                and time.time() - os.stat(self.data_standard_file).st_mtime < 60*60*24:
            with open(self.data_standard_file) as f:
                return json.load(f)
        else:
            data_standard = self._load_data_standard()

            with open(self.data_standard_file, 'w') as f:
                json.dump(data_standard, f, indent=2)

            return data_standard

    def _load_data_standard(self):
        for _ in range(3):
            response = requests.get(self.data_standard_api_url, auth=HTTPBasicAuth(self.client_id, self.api_key))

            if response.status_code == requests.codes.ok:
                try:
                    return response.json()
                except:
                    print 'Response is not JSON: {}'.format(traceback.format_exc())
        else:
            raise Exception('Can not load Data Standard JSON')

    def _get_category(self, data_standard, category_id):
        for category in data_standard['categories']:
            if category_id == category['id']:
                return category

    def _get_categories_path(self, data_standard, category_id):
        categories = data_standard['categories']
        categories = dict((x['id'], x) for x in categories)

        categories_path = []

        while True:
            category = categories[category_id]
            categories_path.append(category['name'])

            category_id = category['parentId']

            if not category_id:
                break

        categories_path.reverse()

        return categories_path[2 if len(categories_path) > 2 else 1:]

    def _get_attributes(self, data_standard, category_id):
        categories = data_standard['categories']
        categories = dict((x['id'], x) for x in categories)

        attributes = data_standard['attributes']
        attributes = dict((x['id'], x) for x in attributes)

        units_of_measure = data_standard['unitsOfMeasure']

        category_attributes = []

        while True:
            category = categories[category_id]

            for category_attribute in category['attributeLinks']:
                attribute = attributes.get(category_attribute['id'])

                if not attribute:
                    print 'Warn: attribute {} does not exist'.format(category_attribute['id'])
                    continue

                new_attribute = copy.deepcopy(category_attribute)
                new_attribute.update(copy.deepcopy(attribute))

                new_attribute['type']['units'] = [units_of_measure[unit_id]['name']
                                                  for unit_id in attribute['type']['units']]

                category_attributes.append(new_attribute)

                if new_attribute['type']['id'] == 'reference':
                    for reference_attribute in new_attribute['attributeLinks']:
                        attribute = attributes.get(reference_attribute['id'])

                        if not attribute:
                            print 'Warn: attribute {} does not exist'.format(reference_attribute['id'])
                            continue

                        new_ref_attrubute = copy.deepcopy(reference_attribute)
                        new_ref_attrubute.update(copy.deepcopy(attribute))

                        new_ref_attrubute['type']['units'] = [units_of_measure[unit_id]['name']
                                                              for unit_id in attribute['type']['units']]

                        new_ref_attrubute['name'] = '{} > {}'.format(new_attribute['name'], new_ref_attrubute['name'])

                        category_attributes.append(new_ref_attrubute)

            category_id = category['parentId']

            if not category_id:
                break

        return category_attributes
