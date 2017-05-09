#!/bin/bash
$@
if [ $? -ne 0 ];then                   # $? holds exit status, test if error occurred
        read -p "Press any key to exit "
fi
exit 0