#!/bin/bash
echo "Create NZB-Monkey source package..."
VERSION=$(grep -m 1 -Po "__version__ = '\K[^']*" src/version.py)
DESTINATION="nzbmonkey-v${VERSION}-linux"
DISTDIR=$PWD/dist
mkdir $DISTDIR 2>/dev/null

echo "$DESTINATION"
mkdir /tmp/$DESTINATION
cp src/*.py /tmp/$DESTINATION
cp src/LICENSE /tmp/$DESTINATION

cd /tmp
tar -cjf "$DISTDIR/$DESTINATION.tbz2" $DESTINATION

rm -rf $DESTINATION
cd $OLDPWD
