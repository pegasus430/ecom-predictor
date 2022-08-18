SUCCESS:

```
#!JSON
{
    "default": {
        "itemsReceived": 1,
        "itemsProcessing": 0,
        "itemDetails": {
            "itemIngestionStatus": [
                {
                    "sku": "062118773504",
                    "index": 0,
                    "wpid": "2UVN8XPPE4DK",
                    "ingestionStatus": "SUCCESS",
                    "ingestionErrors": {
                        "ingestionError": null
                    },
                    "martId": 0
                }
            ]
        },
        "feedStatus": "PROCESSED",
        "feedId": "133f217f-350a-41e2-9e52-09677d1d42f1 ==> SUCCESS",
        "itemsFailed": 0,
        "ingestionErrors": {
            "ingestionError": null
        },
        "offset": 0,
        "limit": 50,
        "itemsSucceeded": 1
    }
}
```
IN PROGRESS
```
HTTP 200 OK
Content-Type: application/json
Vary: Accept
Allow: GET, POST, HEAD, OPTIONS
```
```
#!JSON
{
    "default": {
        "itemsReceived": 24,
        "itemsProcessing": 13,
        "itemDetails": {
            "itemIngestionStatus": [
                {
                    "sku": "00087084936681",
                    "index": 0,
                    "wpid": null,
                    "ingestionStatus": "DATA_ERROR",
                    "ingestionErrors": {
                        "ingestionError": [
                            {
                                "code": "ERR_PDI_0047",
                                "type": "DATA_ERROR",
                                "description": "ID Type=GTIN, ID Value=00087084936681, invalid check-digit in product ID"
                            },
                            {
                                "code": "ERR_PDI_0047",
                                "type": "DATA_ERROR",
                                "description": "ID Type=GTIN, ID Value=00087084936681, invalid check-digit in product ID"
                            }
                        ]
                    },
                    "martId": 0
                },
                {
                    "sku": "00027084953572",
                    "index": 1,
                    "wpid": null,
                    "ingestionStatus": "INPROGRESS",
                    "ingestionErrors": {
                        "ingestionError": null
                    },
                    "martId": 0
                },
                {
                    "sku": "00746775045081",
                    "index": 2,
                    "wpid": null,
                    "ingestionStatus": "INPROGRESS",
                    "ingestionErrors": {
                        "ingestionError": null
                    },
                    "martId": 0
                },
                {
                    "sku": "00746775053512",
                    "index": 3,
                    "wpid": null,
                    "ingestionStatus": "TIMEOUT_ERROR",
                    "ingestionErrors": {
                        "ingestionError": [
                            {
                                "code": "ERR_PDI_0005",
                                "type": "SYSTEM_ERROR",
                                "description": "Unexpected system error occurred in product data setup. Please contact Walmart.com support."
                            }
                        ]
                    },
                    "martId": 0
                },
                {
                    "sku": "00746775200633",
                    "index": 4,
                    "wpid": null,
                    "ingestionStatus": "INPROGRESS",
                    "ingestionErrors": {
                        "ingestionError": null
                    },
                    "martId": 0
                },
                {
                    "sku": "00746775248444",
                    "index": 5,
                    "wpid": null,
                    "ingestionStatus": "INPROGRESS",
                    "ingestionErrors": {
                        "ingestionError": null
                    },
                    "martId": 0
                },
                {
                    "sku": "00887961007077",
                    "index": 6,
                    "wpid": null,
                    "ingestionStatus": "INPROGRESS",
                    "ingestionErrors": {
                        "ingestionError": null
                    },
                    "martId": 0
                },
                {
                    "sku": "00887961057003",
                    "index": 7,
                    "wpid": "112TASFE76QI",
                    "ingestionStatus": "SUCCESS",
                    "ingestionErrors": {
                        "ingestionError": null
                    },
                    "martId": 0
                },
                {
                    "sku": "00887961057010",
                    "index": 8,
                    "wpid": "3MHG3D6C2UIE",
                    "ingestionStatus": "SUCCESS",
                    "ingestionErrors": {
                        "ingestionError": [
                            {
                                "description": null
                            }
                        ]
                    },
                    "martId": 0
                },
                {
                    "sku": "00887961057027",
                    "index": 9,
                    "wpid": null,
                    "ingestionStatus": "TIMEOUT_ERROR",
                    "ingestionErrors": {
                        "ingestionError": [
                            {
                                "code": "ERR_PDI_0005",
                                "type": "SYSTEM_ERROR",
                                "description": "Unexpected system error occurred in product data setup. Please contact Walmart.com support."
                            },
                            {
                                "code": "ERR_PDI_0005",
                                "type": "SYSTEM_ERROR",
                                "description": "Unexpected system error occurred in product data setup. Please contact Walmart.com support."
                            }
                        ]
                    },
                    "martId": 0
                },
                {
                    "sku": "00887961057034",
                    "index": 10,
                    "wpid": null,
                    "ingestionStatus": "INPROGRESS",
                    "ingestionErrors": {
                        "ingestionError": null
                    },
                    "martId": 0
                },
                {
                    "sku": "00887961057041",
                    "index": 11,
                    "wpid": "6HB6OK9UETSO",
                    "ingestionStatus": "SUCCESS",
                    "ingestionErrors": {
                        "ingestionError": [
                            {
                                "description": null
                            }
                        ]
                    },
                    "martId": 0
                },
                {
                    "sku": "00887961057058",
                    "index": 12,
                    "wpid": "6ZI1YWGKI1QF",
                    "ingestionStatus": "SUCCESS",
                    "ingestionErrors": {
                        "ingestionError": null
                    },
                    "martId": 0
                },
                {
                    "sku": "00887961057065",
                    "index": 13,
                    "wpid": null,
                    "ingestionStatus": "INPROGRESS",
                    "ingestionErrors": {
                        "ingestionError": null
                    },
                    "martId": 0
                },
                {
                    "sku": "00887961057072",
                    "index": 14,
                    "wpid": null,
                    "ingestionStatus": "TIMEOUT_ERROR",
                    "ingestionErrors": {
                        "ingestionError": null
                    },
                    "martId": 0
                },
                {
                    "sku": "00887961219876",
                    "index": 15,
                    "wpid": null,
                    "ingestionStatus": "TIMEOUT_ERROR",
                    "ingestionErrors": {
                        "ingestionError": null
                    },
                    "martId": 0
                },
                {
                    "sku": "00887961057096",
                    "index": 16,
                    "wpid": null,
                    "ingestionStatus": "INPROGRESS",
                    "ingestionErrors": {
                        "ingestionError": null
                    },
                    "martId": 0
                },
                {
                    "sku": "00887961057119",
                    "index": 17,
                    "wpid": null,
                    "ingestionStatus": "INPROGRESS",
                    "ingestionErrors": {
                        "ingestionError": null
                    },
                    "martId": 0
                },
                {
                    "sku": "00887961057126",
                    "index": 18,
                    "wpid": null,
                    "ingestionStatus": "INPROGRESS",
                    "ingestionErrors": {
                        "ingestionError": null
                    },
                    "martId": 0
                },
                {
                    "sku": "00887961057133",
                    "index": 19,
                    "wpid": "7F31V9T1JYOX",
                    "ingestionStatus": "SUCCESS",
                    "ingestionErrors": {
                        "ingestionError": [
                            {
                                "description": null
                            }
                        ]
                    },
                    "martId": 0
                },
                {
                    "sku": "00887961057140",
                    "index": 20,
                    "wpid": "33D0S79OM8LG",
                    "ingestionStatus": "SUCCESS",
                    "ingestionErrors": {
                        "ingestionError": null
                    },
                    "martId": 0
                },
                {
                    "sku": "00887961061307",
                    "index": 21,
                    "wpid": null,
                    "ingestionStatus": "INPROGRESS",
                    "ingestionErrors": {
                        "ingestionError": null
                    },
                    "martId": 0
                },
                {
                    "sku": "00887961061314",
                    "index": 22,
                    "wpid": null,
                    "ingestionStatus": "INPROGRESS",
                    "ingestionErrors": {
                        "ingestionError": null
                    },
                    "martId": 0
                },
                {
                    "sku": "00887961157062",
                    "index": 23,
                    "wpid": null,
                    "ingestionStatus": "INPROGRESS",
                    "ingestionErrors": {
                        "ingestionError": null
                    },
                    "martId": 0
                }
            ]
        },
        "feedStatus": "INPROGRESS",
        "feedId": "384a6c5d-248e-41fb-be32-02717d6d7f0f ==> IN PROGRESS",
        "itemsFailed": 5,
        "ingestionErrors": {
            "ingestionError": null
        },
        "offset": 0,
        "limit": 50,
        "itemsSucceeded": 6
    }
}
```

FAILED
```
HTTP 200 OK
Content-Type: application/json
Vary: Accept
Allow: GET, POST, HEAD, OPTIONS
```
```
#!JSON

{
    "default": {
        "itemsReceived": 24,
        "itemsProcessing": 0,
        "itemDetails": {
            "itemIngestionStatus": [
                {
                    "sku": "00087084936681",
                    "index": 0,
                    "wpid": null,
                    "ingestionStatus": "DATA_ERROR",
                    "ingestionErrors": {
                        "ingestionError": [
                            {
                                "code": "ERR_PDI_0047",
                                "type": "DATA_ERROR",
                                "description": "ID Type=GTIN, ID Value=00087084936681, invalid check-digit in product ID"
                            },
                            {
                                "code": "ERR_PDI_0047",
                                "type": "DATA_ERROR",
                                "description": "ID Type=GTIN, ID Value=00087084936681, invalid check-digit in product ID"
                            }
                        ]
                    },
                    "martId": 0
                },
                {
                    "sku": "00027084953572",
                    "index": 1,
                    "wpid": null,
                    "ingestionStatus": "DATA_ERROR",
                    "ingestionErrors": {
                        "ingestionError": [
                            {
                                "code": "ERR_PDI_0003",
                                "type": "DATA_ERROR",
                                "description": "Input XML validation failed.   Expected attribute not found which is followed by:  'countryOfOriginAssembly'. Missing expected attribute name:msrp, \"http://walmart.com/suppliers/\":unitsPerConsumerUnit "
                            },
                            {
                                "code": "ERR_PDI_0003",
                                "type": "DATA_ERROR",
                                "description": "Input XML validation failed.   Expected attribute not found which is followed by:  'countryOfOriginAssembly'. Missing expected attribute name:msrp, \"http://walmart.com/suppliers/\":unitsPerConsumerUnit "
                            }
                        ]
                    },
                    "martId": 0
                },
                {
                    "sku": "00746775045081",
                    "index": 2,
                    "wpid": null,
                    "ingestionStatus": "DATA_ERROR",
                    "ingestionErrors": {
                        "ingestionError": [
                            {
                                "code": "ERR_PDI_0003",
                                "type": "DATA_ERROR",
                                "description": "Input XML validation failed.   Expected attribute not found which is followed by:  'countryOfOriginAssembly'. Missing expected attribute name:msrp, \"http://walmart.com/suppliers/\":unitsPerConsumerUnit "
                            },
                            {
                                "code": "ERR_PDI_0003",
                                "type": "DATA_ERROR",
                                "description": "Input XML validation failed.   Expected attribute not found which is followed by:  'countryOfOriginAssembly'. Missing expected attribute name:msrp, \"http://walmart.com/suppliers/\":unitsPerConsumerUnit "
                            }
                        ]
                    },
                    "martId": 0
                },
                {
                    "sku": "00746775053512",
                    "index": 3,
                    "wpid": null,
                    "ingestionStatus": "DATA_ERROR",
                    "ingestionErrors": {
                        "ingestionError": [
                            {
                                "code": "ERR_PDI_0003",
                                "type": "DATA_ERROR",
                                "description": "Input XML validation failed.   Expected attribute not found which is followed by:  'countryOfOriginAssembly'. Missing expected attribute name:msrp, \"http://walmart.com/suppliers/\":unitsPerConsumerUnit "
                            },
                            {
                                "code": "ERR_PDI_0003",
                                "type": "DATA_ERROR",
                                "description": "Input XML validation failed.   Expected attribute not found which is followed by:  'countryOfOriginAssembly'. Missing expected attribute name:msrp, \"http://walmart.com/suppliers/\":unitsPerConsumerUnit "
                            }
                        ]
                    },
                    "martId": 0
                },
                {
                    "sku": "00746775200633",
                    "index": 4,
                    "wpid": null,
                    "ingestionStatus": "DATA_ERROR",
                    "ingestionErrors": {
                        "ingestionError": [
                            {
                                "code": "ERR_PDI_0003",
                                "type": "DATA_ERROR",
                                "description": "Input XML validation failed.   Expected attribute not found which is followed by:  'countryOfOriginAssembly'. Missing expected attribute name:msrp, \"http://walmart.com/suppliers/\":unitsPerConsumerUnit "
                            },
                            {
                                "code": "ERR_PDI_0003",
                                "type": "DATA_ERROR",
                                "description": "Input XML validation failed.   Expected attribute not found which is followed by:  'countryOfOriginAssembly'. Missing expected attribute name:msrp, \"http://walmart.com/suppliers/\":unitsPerConsumerUnit "
                            }
                        ]
                    },
                    "martId": 0
                },
                {
                    "sku": "00746775248444",
                    "index": 5,
                    "wpid": null,
                    "ingestionStatus": "DATA_ERROR",
                    "ingestionErrors": {
                        "ingestionError": [
                            {
                                "code": "ERR_PDI_0003",
                                "type": "DATA_ERROR",
                                "description": "Input XML validation failed.   Expected attribute not found which is followed by:  'countryOfOriginAssembly'. Missing expected attribute name:msrp, \"http://walmart.com/suppliers/\":unitsPerConsumerUnit "
                            },
                            {
                                "code": "ERR_PDI_0003",
                                "type": "DATA_ERROR",
                                "description": "Input XML validation failed.   Expected attribute not found which is followed by:  'countryOfOriginAssembly'. Missing expected attribute name:msrp, \"http://walmart.com/suppliers/\":unitsPerConsumerUnit "
                            }
                        ]
                    },
                    "martId": 0
                },
                {
                    "sku": "00887961007077",
                    "index": 6,
                    "wpid": null,
                    "ingestionStatus": "DATA_ERROR",
                    "ingestionErrors": {
                        "ingestionError": [
                            {
                                "code": "ERR_PDI_0003",
                                "type": "DATA_ERROR",
                                "description": "Input XML validation failed.   Expected attribute not found which is followed by:  'countryOfOriginAssembly'. Missing expected attribute name:msrp, \"http://walmart.com/suppliers/\":unitsPerConsumerUnit "
                            },
                            {
                                "code": "ERR_PDI_0003",
                                "type": "DATA_ERROR",
                                "description": "Input XML validation failed.   Expected attribute not found which is followed by:  'countryOfOriginAssembly'. Missing expected attribute name:msrp, \"http://walmart.com/suppliers/\":unitsPerConsumerUnit "
                            }
                        ]
                    },
                    "martId": 0
                },
                {
                    "sku": "00887961057003",
                    "index": 7,
                    "wpid": null,
                    "ingestionStatus": "DATA_ERROR",
                    "ingestionErrors": {
                        "ingestionError": [
                            {
                                "code": "ERR_PDI_0003",
                                "type": "DATA_ERROR",
                                "description": "Input XML validation failed.   Expected attribute not found which is followed by:  'countryOfOriginAssembly'. Missing expected attribute name:msrp, \"http://walmart.com/suppliers/\":unitsPerConsumerUnit "
                            },
                            {
                                "code": "ERR_PDI_0003",
                                "type": "DATA_ERROR",
                                "description": "Input XML validation failed.   Expected attribute not found which is followed by:  'countryOfOriginAssembly'. Missing expected attribute name:msrp, \"http://walmart.com/suppliers/\":unitsPerConsumerUnit "
                            }
                        ]
                    },
                    "martId": 0
                },
                {
                    "sku": "00887961057010",
                    "index": 8,
                    "wpid": null,
                    "ingestionStatus": "DATA_ERROR",
                    "ingestionErrors": {
                        "ingestionError": [
                            {
                                "code": "ERR_PDI_0003",
                                "type": "DATA_ERROR",
                                "description": "Input XML validation failed.   Expected attribute not found which is followed by:  'countryOfOriginAssembly'. Missing expected attribute name:msrp, \"http://walmart.com/suppliers/\":unitsPerConsumerUnit "
                            },
                            {
                                "code": "ERR_PDI_0003",
                                "type": "DATA_ERROR",
                                "description": "Input XML validation failed.   Expected attribute not found which is followed by:  'countryOfOriginAssembly'. Missing expected attribute name:msrp, \"http://walmart.com/suppliers/\":unitsPerConsumerUnit "
                            }
                        ]
                    },
                    "martId": 0
                },
                {
                    "sku": "00887961057027",
                    "index": 9,
                    "wpid": null,
                    "ingestionStatus": "DATA_ERROR",
                    "ingestionErrors": {
                        "ingestionError": [
                            {
                                "code": "ERR_PDI_0003",
                                "type": "DATA_ERROR",
                                "description": "Input XML validation failed.   Expected attribute not found which is followed by:  'countryOfOriginAssembly'. Missing expected attribute name:msrp, \"http://walmart.com/suppliers/\":unitsPerConsumerUnit "
                            },
                            {
                                "code": "ERR_PDI_0003",
                                "type": "DATA_ERROR",
                                "description": "Input XML validation failed.   Expected attribute not found which is followed by:  'countryOfOriginAssembly'. Missing expected attribute name:msrp, \"http://walmart.com/suppliers/\":unitsPerConsumerUnit "
                            }
                        ]
                    },
                    "martId": 0
                },
                {
                    "sku": "00887961057034",
                    "index": 10,
                    "wpid": null,
                    "ingestionStatus": "DATA_ERROR",
                    "ingestionErrors": {
                        "ingestionError": [
                            {
                                "code": "ERR_PDI_0003",
                                "type": "DATA_ERROR",
                                "description": "Input XML validation failed.   Expected attribute not found which is followed by:  'countryOfOriginAssembly'. Missing expected attribute name:msrp, \"http://walmart.com/suppliers/\":unitsPerConsumerUnit "
                            },
                            {
                                "code": "ERR_PDI_0003",
                                "type": "DATA_ERROR",
                                "description": "Input XML validation failed.   Expected attribute not found which is followed by:  'countryOfOriginAssembly'. Missing expected attribute name:msrp, \"http://walmart.com/suppliers/\":unitsPerConsumerUnit "
                            }
                        ]
                    },
                    "martId": 0
                },
                {
                    "sku": "00887961057041",
                    "index": 11,
                    "wpid": null,
                    "ingestionStatus": "DATA_ERROR",
                    "ingestionErrors": {
                        "ingestionError": [
                            {
                                "code": "ERR_PDI_0003",
                                "type": "DATA_ERROR",
                                "description": "Input XML validation failed.   Expected attribute not found which is followed by:  'countryOfOriginAssembly'. Missing expected attribute name:msrp, \"http://walmart.com/suppliers/\":unitsPerConsumerUnit "
                            },
                            {
                                "code": "ERR_PDI_0003",
                                "type": "DATA_ERROR",
                                "description": "Input XML validation failed.   Expected attribute not found which is followed by:  'countryOfOriginAssembly'. Missing expected attribute name:msrp, \"http://walmart.com/suppliers/\":unitsPerConsumerUnit "
                            }
                        ]
                    },
                    "martId": 0
                },
                {
                    "sku": "00887961057058",
                    "index": 12,
                    "wpid": null,
                    "ingestionStatus": "DATA_ERROR",
                    "ingestionErrors": {
                        "ingestionError": [
                            {
                                "code": "ERR_PDI_0003",
                                "type": "DATA_ERROR",
                                "description": "Input XML validation failed.   Expected attribute not found which is followed by:  'countryOfOriginAssembly'. Missing expected attribute name:msrp, \"http://walmart.com/suppliers/\":unitsPerConsumerUnit "
                            },
                            {
                                "code": "ERR_PDI_0003",
                                "type": "DATA_ERROR",
                                "description": "Input XML validation failed.   Expected attribute not found which is followed by:  'countryOfOriginAssembly'. Missing expected attribute name:msrp, \"http://walmart.com/suppliers/\":unitsPerConsumerUnit "
                            }
                        ]
                    },
                    "martId": 0
                },
                {
                    "sku": "00887961057065",
                    "index": 13,
                    "wpid": null,
                    "ingestionStatus": "DATA_ERROR",
                    "ingestionErrors": {
                        "ingestionError": [
                            {
                                "code": "ERR_PDI_0003",
                                "type": "DATA_ERROR",
                                "description": "Input XML validation failed.   Expected attribute not found which is followed by:  'countryOfOriginAssembly'. Missing expected attribute name:msrp, \"http://walmart.com/suppliers/\":unitsPerConsumerUnit "
                            },
                            {
                                "code": "ERR_PDI_0003",
                                "type": "DATA_ERROR",
                                "description": "Input XML validation failed.   Expected attribute not found which is followed by:  'countryOfOriginAssembly'. Missing expected attribute name:msrp, \"http://walmart.com/suppliers/\":unitsPerConsumerUnit "
                            }
                        ]
                    },
                    "martId": 0
                },
                {
                    "sku": "00887961057072",
                    "index": 14,
                    "wpid": null,
                    "ingestionStatus": "DATA_ERROR",
                    "ingestionErrors": {
                        "ingestionError": [
                            {
                                "code": "ERR_PDI_0003",
                                "type": "DATA_ERROR",
                                "description": "Input XML validation failed.   Expected attribute not found which is followed by:  'countryOfOriginAssembly'. Missing expected attribute name:msrp, \"http://walmart.com/suppliers/\":unitsPerConsumerUnit "
                            },
                            {
                                "code": "ERR_PDI_0003",
                                "type": "DATA_ERROR",
                                "description": "Input XML validation failed.   Expected attribute not found which is followed by:  'countryOfOriginAssembly'. Missing expected attribute name:msrp, \"http://walmart.com/suppliers/\":unitsPerConsumerUnit "
                            }
                        ]
                    },
                    "martId": 0
                },
                {
                    "sku": "00887961219876",
                    "index": 15,
                    "wpid": null,
                    "ingestionStatus": "DATA_ERROR",
                    "ingestionErrors": {
                        "ingestionError": [
                            {
                                "code": "ERR_PDI_0003",
                                "type": "DATA_ERROR",
                                "description": "Input XML validation failed.   Expected attribute not found which is followed by:  'countryOfOriginAssembly'. Missing expected attribute name:msrp, \"http://walmart.com/suppliers/\":unitsPerConsumerUnit "
                            },
                            {
                                "code": "ERR_PDI_0003",
                                "type": "DATA_ERROR",
                                "description": "Input XML validation failed.   Expected attribute not found which is followed by:  'countryOfOriginAssembly'. Missing expected attribute name:msrp, \"http://walmart.com/suppliers/\":unitsPerConsumerUnit "
                            }
                        ]
                    },
                    "martId": 0
                },
                {
                    "sku": "00887961057096",
                    "index": 16,
                    "wpid": null,
                    "ingestionStatus": "DATA_ERROR",
                    "ingestionErrors": {
                        "ingestionError": [
                            {
                                "code": "ERR_PDI_0003",
                                "type": "DATA_ERROR",
                                "description": "Input XML validation failed.   Expected attribute not found which is followed by:  'countryOfOriginAssembly'. Missing expected attribute name:msrp, \"http://walmart.com/suppliers/\":unitsPerConsumerUnit "
                            },
                            {
                                "code": "ERR_PDI_0003",
                                "type": "DATA_ERROR",
                                "description": "Input XML validation failed.   Expected attribute not found which is followed by:  'countryOfOriginAssembly'. Missing expected attribute name:msrp, \"http://walmart.com/suppliers/\":unitsPerConsumerUnit "
                            }
                        ]
                    },
                    "martId": 0
                },
                {
                    "sku": "00887961057119",
                    "index": 17,
                    "wpid": null,
                    "ingestionStatus": "DATA_ERROR",
                    "ingestionErrors": {
                        "ingestionError": [
                            {
                                "code": "ERR_PDI_0003",
                                "type": "DATA_ERROR",
                                "description": "Input XML validation failed.   Expected attribute not found which is followed by:  'countryOfOriginAssembly'. Missing expected attribute name:msrp, \"http://walmart.com/suppliers/\":unitsPerConsumerUnit "
                            },
                            {
                                "code": "ERR_PDI_0003",
                                "type": "DATA_ERROR",
                                "description": "Input XML validation failed.   Expected attribute not found which is followed by:  'countryOfOriginAssembly'. Missing expected attribute name:msrp, \"http://walmart.com/suppliers/\":unitsPerConsumerUnit "
                            }
                        ]
                    },
                    "martId": 0
                },
                {
                    "sku": "00887961057126",
                    "index": 18,
                    "wpid": null,
                    "ingestionStatus": "DATA_ERROR",
                    "ingestionErrors": {
                        "ingestionError": [
                            {
                                "code": "ERR_PDI_0003",
                                "type": "DATA_ERROR",
                                "description": "Input XML validation failed.   Expected attribute not found which is followed by:  'countryOfOriginAssembly'. Missing expected attribute name:msrp, \"http://walmart.com/suppliers/\":unitsPerConsumerUnit "
                            },
                            {
                                "code": "ERR_PDI_0003",
                                "type": "DATA_ERROR",
                                "description": "Input XML validation failed.   Expected attribute not found which is followed by:  'countryOfOriginAssembly'. Missing expected attribute name:msrp, \"http://walmart.com/suppliers/\":unitsPerConsumerUnit "
                            }
                        ]
                    },
                    "martId": 0
                },
                {
                    "sku": "00887961057133",
                    "index": 19,
                    "wpid": null,
                    "ingestionStatus": "DATA_ERROR",
                    "ingestionErrors": {
                        "ingestionError": [
                            {
                                "code": "ERR_PDI_0003",
                                "type": "DATA_ERROR",
                                "description": "Input XML validation failed.   Expected attribute not found which is followed by:  'countryOfOriginAssembly'. Missing expected attribute name:msrp, \"http://walmart.com/suppliers/\":unitsPerConsumerUnit "
                            },
                            {
                                "code": "ERR_PDI_0003",
                                "type": "DATA_ERROR",
                                "description": "Input XML validation failed.   Expected attribute not found which is followed by:  'countryOfOriginAssembly'. Missing expected attribute name:msrp, \"http://walmart.com/suppliers/\":unitsPerConsumerUnit "
                            }
                        ]
                    },
                    "martId": 0
                },
                {
                    "sku": "00887961057140",
                    "index": 20,
                    "wpid": null,
                    "ingestionStatus": "DATA_ERROR",
                    "ingestionErrors": {
                        "ingestionError": [
                            {
                                "code": "ERR_PDI_0003",
                                "type": "DATA_ERROR",
                                "description": "Input XML validation failed.   Expected attribute not found which is followed by:  'countryOfOriginAssembly'. Missing expected attribute name:msrp, \"http://walmart.com/suppliers/\":unitsPerConsumerUnit "
                            },
                            {
                                "code": "ERR_PDI_0003",
                                "type": "DATA_ERROR",
                                "description": "Input XML validation failed.   Expected attribute not found which is followed by:  'countryOfOriginAssembly'. Missing expected attribute name:msrp, \"http://walmart.com/suppliers/\":unitsPerConsumerUnit "
                            }
                        ]
                    },
                    "martId": 0
                },
                {
                    "sku": "00887961061307",
                    "index": 21,
                    "wpid": null,
                    "ingestionStatus": "DATA_ERROR",
                    "ingestionErrors": {
                        "ingestionError": [
                            {
                                "code": "ERR_PDI_0003",
                                "type": "DATA_ERROR",
                                "description": "Input XML validation failed.   Expected attribute not found which is followed by:  'countryOfOriginAssembly'. Missing expected attribute name:msrp, \"http://walmart.com/suppliers/\":unitsPerConsumerUnit "
                            },
                            {
                                "code": "ERR_PDI_0003",
                                "type": "DATA_ERROR",
                                "description": "Input XML validation failed.   Expected attribute not found which is followed by:  'countryOfOriginAssembly'. Missing expected attribute name:msrp, \"http://walmart.com/suppliers/\":unitsPerConsumerUnit "
                            }
                        ]
                    },
                    "martId": 0
                },
                {
                    "sku": "00887961061314",
                    "index": 22,
                    "wpid": null,
                    "ingestionStatus": "DATA_ERROR",
                    "ingestionErrors": {
                        "ingestionError": [
                            {
                                "code": "ERR_PDI_0003",
                                "type": "DATA_ERROR",
                                "description": "Input XML validation failed.   Expected attribute not found which is followed by:  'countryOfOriginAssembly'. Missing expected attribute name:msrp, \"http://walmart.com/suppliers/\":unitsPerConsumerUnit "
                            },
                            {
                                "code": "ERR_PDI_0003",
                                "type": "DATA_ERROR",
                                "description": "Input XML validation failed.   Expected attribute not found which is followed by:  'countryOfOriginAssembly'. Missing expected attribute name:msrp, \"http://walmart.com/suppliers/\":unitsPerConsumerUnit "
                            }
                        ]
                    },
                    "martId": 0
                },
                {
                    "sku": "00887961157062",
                    "index": 23,
                    "wpid": null,
                    "ingestionStatus": "DATA_ERROR",
                    "ingestionErrors": {
                        "ingestionError": [
                            {
                                "code": "ERR_PDI_0003",
                                "type": "DATA_ERROR",
                                "description": "Input XML validation failed.   Expected attribute not found which is followed by:  'countryOfOriginAssembly'. Missing expected attribute name:msrp, \"http://walmart.com/suppliers/\":unitsPerConsumerUnit "
                            },
                            {
                                "code": "ERR_PDI_0003",
                                "type": "DATA_ERROR",
                                "description": "Input XML validation failed.   Expected attribute not found which is followed by:  'countryOfOriginAssembly'. Missing expected attribute name:msrp, \"http://walmart.com/suppliers/\":unitsPerConsumerUnit "
                            }
                        ]
                    },
                    "martId": 0
                }
            ]
        },
        "feedStatus": "PROCESSED",
        "feedId": "8469b76a-4449-4053-84b9-2896096098b4 ==> FAILED",
        "itemsFailed": 24,
        "ingestionErrors": {
            "ingestionError": [
                {
                    "code": "ERR_PDI_0001",
                    "type": "DATA_ERROR",
                    "description": "com.walmart.partnerapi.exception.PartnerDataProcessingException: There is not a single eligible item found in feed to process"
                }
            ]
        },
        "offset": 0,
        "limit": 50,
        "itemsSucceeded": 0
    }
}
```