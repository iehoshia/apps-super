#!/bin/sh

#---------------------------------------------------------
#    Script for Update POS to last version
# --------------------------------------------------------

# Main functions/variables declaration


cd /home/$USER/.pos_app/ 

hg pull && hg update


cd neo

hg pull && hg update
