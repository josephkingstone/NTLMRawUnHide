#!/usr/bin/env python3
# 
# NTLMRawUnhide.py is a Python3 script designed to parse network packet capture 
# files and extract NTLMv2 hashes in a crackable format. The following binary 
# network packet capture formats are supported: *.pcap *.pcapng *.cap *.etl
# 
# This tool was developed to extract NTLMv2 hashes from files generated by 
# native Windows binaries like NETSH.EXE and PKTMON.EXE without conversion.
#
#
# Usage: NTLMRawUnhide.py -i <inputfile> [-o <outputfile>] [-f] [-h] [-q] [-v]
#
#
# Methods to create compatible packet capture files:
#
# > Wireshark: Set capture filter as "tcp port 445"; Save as .pcapng
#
# > tcpdump -i eth0 -w capture.pcap "port 445"
#
# > netsh.exe trace start persistent=yes capture=yes TCP.AnyPort=445 \
#        tracefile=C:\Users\Public\capture.etl
#   netsh.exe trace stop
#
# > pktmon.exe filter add SMB -p 445
#   :: List all filters 
#   pktmon.exe filter list
#   :: Find id of the network adapter (example > Id: 9)
#   pktmon.exe comp list
#   :: pktmon.exe start --etw -p 0 -c [Adapter ID]     
#   pktmon.exe start --etw -p 0 -c 9 
#   :: Will create the file PktMon.etl in current directory
#   pktmon.exe stop
#   :: Cleanup
#   pktmon.exe filter remove
#
#
# Author:   Mike Gualtieri
# Blog:     https://www.mike-gualtieri.com
# Twitter:  https://twitter.com/mlgualtieri
#
# GitHub:   https://github.com/mlgualtieri/NTLMRawUnhide
#
#
# The following URL was very helpful when building this tool:
#     The NTLM Authentication Protocol and Security Support Provider
#     http://davenport.sourceforge.net/ntlm.html
#

import sys, getopt, time
import os.path
from os import path



# The decode_string() function was taken from: 
# https://github.com/b17zr/ntlm_challenger
def decode_string(byte_string):
    return byte_string.decode('UTF-8').replace('\x00', '')


# The decode_int() function was taken from: 
# https://github.com/b17zr/ntlm_challenger
def decode_int(byte_string):
    return int.from_bytes(byte_string, 'little')


# Output our hash to specified outfile
def writeOutfile(output, outstr):
    outstr = outstr + "\n"
    f = open(output, "a")
    f.write(outstr)
    f.close()



# All the magic happens in searchCaptureFile()
def searchCaptureFile(infile, outfile, verbose, follow, quiet, offset = 0):
    
    # Variable initialization
    server_challenge = None


    # NTLMSSP message signatures
    ntlmssp_sig    = b'\x4e\x54\x4c\x4d\x53\x53\x50\x00'	            # NTLMSSP\x00
    ntlmssp_type_1 = b'\x4e\x54\x4c\x4d\x53\x53\x50\x00\x01\x00\x00\x00'    # NTLMSSP\x00 0x01000000
    ntlmssp_type_2 = b'\x4e\x54\x4c\x4d\x53\x53\x50\x00\x02\x00\x00\x00'    # NTLMSSP\x00 0x02000000
    ntlmssp_type_3 = b'\x4e\x54\x4c\x4d\x53\x53\x50\x00\x03\x00\x00\x00'    # NTLMSSP\x00 0x03000000
 


    # Read binary file data
    with open(infile, 'rb') as fp:
        readbuff = fp.read()
        last_byte = len(readbuff)

        #fp.seek(offset,0)
        fp.seek(0,0)
        readbuff = fp.read()



    # Read bytes until the end of the file
    while offset != -1:
        #print("Current scan offset:",offset)
    
        # increment file offset past occurance of ntlm_sig unless start of file
        if offset != 0:
            offset = offset + len(ntlmssp_sig)
    
        offset = readbuff.find(ntlmssp_sig, offset) 
    
    
    
        ### Check for NTLMSSP Message type(s)
    
        # NTLMSSP Message Type 1: Negotiation
        check_ntlm_type = readbuff.find(ntlmssp_type_1, offset, offset + len(ntlmssp_type_1))
        if check_ntlm_type > -1:
            if quiet == False:
                if verbose == True:
                    print("\033[1;37mFound NTLMSSP Message Type 1 :\033[1;32m Negotiation\033[0;37m    \033[1;30m>\033[0;37m Offset", offset,'\033[0;37m')
                else:
                    print("\033[1;37mFound NTLMSSP Message Type 1 :\033[1;32m Negotiation\033[0;37m")
                print()
 


        # NTLMSSP Message Type 2: Challenge
        check_ntlm_type = readbuff.find(ntlmssp_type_2, offset, offset + len(ntlmssp_type_2))
        if check_ntlm_type > -1:
            server_challenge = readbuff[(offset+24):(offset+32)]

            if quiet == False:
                if verbose == True:
                    print("\033[1;37mFound NTLMSSP Message Type 2 :\033[1;32m Challenge      \033[1;30m>\033[0;37m Offset", offset,'\033[0;37m')
                else:
                    print("\033[1;37mFound NTLMSSP Message Type 2 :\033[1;32m Challenge\033[0;37m")


                print("    \033[1;34m>\033[1;37m Server Challenge       :\033[0;97m", server_challenge.hex(),'\033[0;37m')
                print()
 


        # NTLMSSP Message Type 3: Authentication
        check_ntlm_type = readbuff.find(ntlmssp_type_3, offset, offset + len(ntlmssp_type_3))
        if check_ntlm_type > -1:
            if quiet == False:
                if verbose == True:
                    print("\033[1;37mFound NTLMSSP Message Type 3 :\033[1;32m Authentication \033[1;30m>\033[0;37m Offset", offset,'\033[0;37m')
                else:
                    print("\033[1;37mFound NTLMSSP Message Type 3 :\033[1;32m Authentication\033[0;37m")
    
            # Find domain
            domain_length_raw = readbuff[(offset+28):(offset+28+2)]
            domain_length     = decode_int(domain_length_raw)
    
            domain_offset_raw = readbuff[(offset+28+2+2):(offset+28+2+2+4)]
            domain_offset     = decode_int(domain_offset_raw)
    
            domain = readbuff[(offset + domain_offset):(offset + domain_offset + domain_length)]

            if quiet == False:
                print("    \033[1;34m>\033[1;37m Domain                 :\033[0;97m", decode_string(domain),'\033[0;37m')

                if verbose == True:
                    print("      Domain length          :", domain_length)
                    print("      Domain offset          :", domain_offset)
                    print()
    
    
            # Find username
            username_length_raw = readbuff[(offset+36):(offset+36+2)]
            username_length     = decode_int(username_length_raw)
    
            username_offset_raw = readbuff[(offset+36+2+2):(offset+36+2+2+4)]
            username_offset     = decode_int(username_offset_raw)
    
            username = readbuff[(offset + username_offset):(offset + username_offset + username_length)]

            if quiet == False:
                print("    \033[1;34m>\033[1;37m Username               :\033[0;97m", decode_string(username),'\033[0;37m')

                if verbose == True:
                    print("      Username length        :", username_length)
                    print("      Username offset        :", username_offset)
                    print()
    
            # Find workstation
            workstation_length_raw = readbuff[(offset+44):(offset+44+2)]
            workstation_length     = decode_int(workstation_length_raw)
    
            workstation_offset_raw = readbuff[(offset+44+2+2):(offset+44+2+2+4)]
            workstation_offset     = decode_int(workstation_offset_raw)
    
            workstation = readbuff[(offset + workstation_offset):(offset + workstation_offset + workstation_length)]

            if quiet == False:
                print("    \033[1;34m>\033[1;37m Workstation            :\033[0;97m", decode_string(workstation),'\033[0;37m')

                if verbose == True:
                    print("      Workstation length     :", workstation_length)
                    print("      Workstation offset     :", workstation_offset)
                    print()
    
    
            # Find NTLM response
            ntlm_length_raw = readbuff[(offset+20):(offset+20+2)]
            ntlm_length     = decode_int(ntlm_length_raw)
    
            ntlm_offset_raw = readbuff[(offset+20+2+2):(offset+20+2+2+4)]
            ntlm_offset     = decode_int(ntlm_offset_raw)
    
            ntproofstr      = readbuff[(offset + ntlm_offset):(offset + ntlm_offset + 16)]
            ntlmv2_response = readbuff[(offset + ntlm_offset + 16):(offset + ntlm_offset + ntlm_length)]

            if quiet == False:
                if verbose == True:
                    print("      NTLM length            :", ntlm_length)
                    print("      NTLM offset            :", ntlm_offset)
                    print("    \033[1;34m>\033[1;37m NTProofStr             :\033[0;37m", ntproofstr.hex())
                    print("    \033[1;34m>\033[1;37m NTLMv2 Response        :\033[0;37m", ntlmv2_response.hex())
    
                print()
    

            # Prepare NTLMv2 Hash for output
            if server_challenge != None:
                if quiet == False:
                    print("\033[1;37mNTLMv2 Hash recovered:\033[0;97m")

                if ntlm_length == 0:
                    if quiet == False:
                        print("\033[0;37mNTLM NULL session found... no hash to generate\033[0;37m")
                elif domain_length == 0:
                    hash_out = decode_string(username) +"::"+ decode_string(workstation) +":"+ server_challenge.hex() +":"+ ntproofstr.hex() +":"+ ntlmv2_response.hex()

                    print(hash_out)
                    if outfile != '':
                        writeOutfile(output, hash_out)
                else:
                    hash_out = decode_string(domain) +"\\"+ decode_string(username) +"::"+ decode_string(workstation) +":"+ server_challenge.hex() +":"+ ntproofstr.hex() +":"+ ntlmv2_response.hex()
                    print(hash_out)
                    if outfile != '':
                        writeOutfile(outfile, hash_out)

                print()

                # Reset variable 
                server_challenge = None
            else:
                if quiet == False:
                    print("\033[1;31mServer Challenge not found... can't create crackable hash :-/\033[0;37m")
                    print()

    fp.close()


    # Continue forever if follow is set, until ctrl-c
    if follow == True:
        try:
            time.sleep(1)
            searchCaptureFile(infile, outfile, verbose, follow, quiet, last_byte)
        except KeyboardInterrupt:
            # Gracefully exit on ctrl-c
            print("Bye!")
            pass






# Can a tool be a tool without ASCII Art?
def banner():
    # Start yellow
    print('\033[0;93m                                                              /%(')
    print('                               -= Find NTLMv2 =-          ,@@@@@@@@&')
    print('           /%&@@@@&,            -= hashes w/ =-          %@@@@@@@@@@@*')
    print('         (@@@@@@@@@@@(       -= NTLMRawUnHide.py =-    *@@@@@@@@@@@@@@@.')
    print('        &@@@@@@@@@@@@@@&.                             @@@@@@@@@@@@@@@@@@(')
    print('      ,@@@@@@@@@@@@@@@@@@@/                        .%@@@@@@@@@@@@@@@@@@@@@')
    print('     /@@@@@@@#&@&*.,/@@@@(.                            ,%@@@@&##(%@@@@@@@@@.')
    print('    (@@@@@@@(##(.         .#&@%%(                .&&@@&(            ,/@@@@@@#')
    print('   %@@@@@@&*/((.         #(                           ,(@&            ,%@@@@@@*')
    print('  @@@@@@@&,/(*                                           ,             .,&@@@@@#')
    print(' @@@@@@@/*//,                                                            .,,,**')
    print('   .,,  ...')
    print('                                    .#@@@@@@@(.')
    print('                                   /@@@@@@@@@@@&')
    print('                                   .@@@@@@@@@@@*')
    print('                                     .(&@@@%/.  ..')
    print('                               (@@&     %@@.   .@@@,')
    print('                          /@@#          @@@,         %@&')
    print('                               &@@&.    @@@/    @@@#')
    print('                          .    %@@@(   ,@@@#    @@@(     ,')
    print('                         *@@/         .@@@@@(          #@%')
    print('                          *@@%.      &@@@@@@@@,      /@@@.')
    print('                           .@@@@@@@@@@@&. .*@@@@@@@@@@@/.')
    print('                              .%@@@@%,        /%@@@&(.')
    print()
    # Regular white text
    print('\033[0;97m')



# Print basic usage
def usage():
    # Bold white text
    print('\033[1;37m')
    print('usage: NTLMRawUnHide.py -i <inputfile> [-o <outputfile>] [-f] [-h] [-q] [-v]')
    # Regular white text
    print('\033[0;97m')


# Display verbose help
def showhelp():
    usage()
    print('Main options:')
    print('  -f, --follow               Continuously "follow" (e.g. "read from")')
    print('                             input file for new data')
    print('  -h, --help')
    print('  -i, --input  <inputfile>   Binary packet data input file')
    print('                             (.pcap, .pcapng, .cap, .etl, others?)')
    print('  -o, --output <outputfile>  Output file to record any found NTLM')
    print('                             hashes')
    print('  -q, --quiet                Be a lot more quiet and only output')
    print('                             found NTLM hashes. --quiet will also')
    print('                             disable verbose, if specified.')
    print('  -v, --verbose')
    print()




def main(argv):

    # Check to see if command line args were sent
    if not argv:
        banner()
        usage()
        sys.exit()


    # Default option values
    infile  = ''
    outfile = ''
    verbose = False
    follow  = False
    quiet   = False


    # Process command line args
    try:
        opts, args = getopt.getopt(argv,"hvqfi:o:",["input=","output=","verbose","follow","quiet"])
    except getopt.GetoptError:
        usage()
        sys.exit(2)
    for opt, arg in opts:
        if opt in ('-h','--help'):
            banner()
            showhelp()
            sys.exit()
        elif opt in ("-i", "--input"):
            infile = arg
        elif opt in ("-o", "--output"):
            outfile = arg
        elif opt in ("-f", "--follow"):
            follow  = True
        elif opt in ("-v", "--verbose"):
            verbose = True
        elif opt in ("-q", "--quiet"):
            quiet = True
        else:
            usage()
            sys.exit(2)


    # Check to make sure input file is specified
    if infile == "":
        print("\033[1;31m[!]\033[0;97m Error: Input file not specified.  Did you mean to specify -i?")
        sys.exit()


    # Check to make sure input file exists
    if os.path.exists(infile) == False:
        print("\033[1;31m[!]\033[0;97m Error: Input file not found.")
        sys.exit()


    if quiet == True:
        # Ensure we will be quiet
        verbose = False;
    else:
        banner()


    # If infile is specified, get things kicked off 
    if infile != '':
        # Bold white text
        print("\033[1;37mSearching", infile, "for NTLMv2 hashes...")

        if outfile != '':
            print('Writing output to:', outfile)

        # Regular white text
        print('\033[0;97m')
        searchCaptureFile(infile, outfile, verbose, follow, quiet, 0)



if __name__ == "__main__":
    main(sys.argv[1:])



