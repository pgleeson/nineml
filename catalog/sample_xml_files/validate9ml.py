###
#   Utility script to validate any file or folder of *.nml files against the NeuroML 2 schema
###

import sys

for file in sys.argv[1:]:


    from lxml import etree
    from urllib import urlopen

    loc = "https://raw.github.com/pgleeson/nineml/master/catalog/sample_xml_files/NineML_v0.2.xsd"
    schema_file = urlopen(loc)

    xmlschema_doc = etree.parse(schema_file)
    xmlschema = etree.XMLSchema(xmlschema_doc)

    print "Validating %s against %s" %(file, loc)

    doc = etree.parse(file)
    xmlschema.assertValid(doc)
    print "It's valid!"
