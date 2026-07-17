#!/bin/bash

# this causes an error SC2045: Iterating over ls output is fragile.
for f in $(ls /var/lib/potos); do
  echo "$f"
done
