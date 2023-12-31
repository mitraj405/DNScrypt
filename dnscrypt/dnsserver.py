import socket, glob, json
from ecies.utils import generate_eth_key, generate_key
from ecies import encrypt, decrypt
import os
from cryptography.fernet import Fernet

port = 443
ip = '127.0.0.1'

key =b'qTzU6xFZbbEJpIRJJE_ac2_K_denXxuTuwVvcs3YbYQ='
fernet = Fernet(key)

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((ip, port))

def load_zones():

    jsonzone = {}
    zonefiles = glob.glob('zones/*.zone')

    for zone in zonefiles:
        with open(zone) as zonedata:
            data = json.load(zonedata)
            zonename = data["$origin"]
            #print("the decrypted hostname server hsa got is " + str(zonename))
            jsonzone[zonename] = data
    return jsonzone

zonedata = load_zones()

def getflags(flags):

    byte1 = bytes(flags[:1])
    byte2 = bytes(flags[1:2])

    rflags = ''

    QR = '1'

    OPCODE = ''
    for bit in range(1,5):
        OPCODE += str(ord(byte1)&(1<<bit))

    AA = '1'

    TC = '0'

    RD = '0'

    # Byte 2

    RA = '0'

    Z = '000'

    RCODE = '0000'

    return int(QR+OPCODE+AA+TC+RD, 2).to_bytes(1, byteorder='big')+int(RA+Z+RCODE, 2).to_bytes(1, byteorder='big')

def getquestiondomain(data):

    state = 0
    expectedlength = 0
    domainstring = ''
    domainparts = []
    x = 0
    y = 0
    for byte in data:
        if state == 1:
            if byte != 0:
                domainstring += chr(byte)
            x += 1
            if x == expectedlength:
                domainparts.append(domainstring)
                domainstring = ''
                state = 0
                x = 0
            if byte == 0:
                domainparts.append(domainstring)
                break
        else:
            state = 1
            expectedlength = byte
        y += 1

    questiontype = data[y:y+2]

    return (domainparts, questiontype)

def getzone(domain):
    global zonedata

    return zonedata[domain]


def getrecs(data):
    domain1, questiontype = getquestiondomain(data)
    qt = ''
    if questiontype == b'\x00\x01':
        qt = 'a'
	
    key =b'qTzU6xFZbbEJpIRJJE_ac2_K_denXxuTuwVvcs3YbYQ='
    fernet = Fernet(key)

    domain = fernet.decrypt(domain1[0].encode()).decode()
    
    zone = getzone(domain)
    
    return (zone[qt], qt, domain)
    
    
def buildquestion(domainname, rectype):
    qbytes = b''

    for part in domainname:
        length = len(part)
        qbytes += bytes([length])

        for char in part:
            qbytes += ord(char).to_bytes(1, byteorder='big')

    if rectype == 'a':
        qbytes += (1).to_bytes(2, byteorder='big')

    qbytes += (1).to_bytes(2, byteorder='big')

    return qbytes

def rectobytes(domainname, rectype, recttl, recval):

    rbytes = b'\xc0\x0c'

    if rectype == 'a':
        rbytes = rbytes + bytes([0]) + bytes([1])

    rbytes = rbytes + bytes([0]) + bytes([1])

    rbytes += int(recttl).to_bytes(4, byteorder='big')

    if rectype == 'a':
        rbytes = rbytes + bytes([0]) + bytes([4]);rbytes += bytes(recval)
            
    return rbytes


def buildresponse(data):

    TransactionID = data[:2]

    # Get the flags
    Flags = getflags(data[2:4])

    # Question Count
    QDCOUNT = b'\x00\x01'

    # Answer Count
    ANCOUNT = len(getrecs(data[12:])[0]).to_bytes(2, byteorder='big')

    # Nameserver Count
    NSCOUNT = (0).to_bytes(2, byteorder='big')

    # Additonal Count
    ARCOUNT = (0).to_bytes(2, byteorder='big')

    dnsheader = TransactionID+Flags+QDCOUNT+ANCOUNT+NSCOUNT+ARCOUNT

    # Create DNS body
    dnsbody = b''

    # Get answer for query
    records, rectype, domainname = getrecs(data[12:])

    dnsquestion = buildquestion(['secret', 'org', ''], rectype)

    for record in records:
        dnsbody += rectobytes(['secret', 'org', ''], rectype, record["ttl"], fernet.encrypt(str(record["value"]).encode()))  

    print("decrypted domain name dns server has found is " + str(domainname))
    return dnsheader + dnsquestion + dnsbody 



while 1:
    data, addr = sock.recvfrom(512)
    print("listening...")
    r = buildresponse(data)
    sock.sendto(r, addr)
