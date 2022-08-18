# How to store cluster names in S3 file?

There is a configuration json file for auto scale groups.


Amazon S3 bucket name - "sc-settings"

file name - "autoscale_groups.cfg"

It is a json file and it contains 'groups' in its json structure.
We can define cluster names there.

## autoscale_groups.cfg
```
{
  "groups": [
    "SCCluster1",
    "SCCluster2", 
    "SCCluster3", 
    "SCCluster4"
  ]
  ,...
}
```
