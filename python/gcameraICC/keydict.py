KeysDictionary('gcamera',(0, 1),
               Key("text", String(help="text for humans")),
               Key("simulating", 
                   Enum('On', 'Off', help="Are we reading simulated/historical data, or taking new images?"),
                   String(help="directory from which simulations are reading data."),
                   Int(help="sequence number of the last read image")),
               Key("exposureState", 
                   Enum('idle','integrating','reading','done','aborted'),
                   Float(help="remaining time for this state (sec; 0 if none, short or unknown)"),
                   Float(help="total time for this state (sec; 0 if none, short or unknown)")),
               Key("filename", 
                   String(help='last read file'))
               )
                       
