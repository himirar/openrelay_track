#!/usr/bin/python

"""
- Tests for open mail relay + DNS
- Multiprocess
- File lock 
- Safe interrupt
- Deps: python-dns
"""

import signal, sys, re, os, socket, time, smtplib
from  multiprocessing import Pool, Value, Lock
import dns.resolver
#from itertools import repeat

processess = 10  #MP processes
log_file = '/var/log/ord.log'
Query = 'www.google.com'

#Sig.handler
def _signal_handler_(signal, frame):
  print "Kill workers and process group(pgid): "+str(os.getpgrp())
  os.killpg(os.getpgrp(),9)
  sys.exit(0)

#signal.signal(signal.SIGINT, _signal_handler_) #SIGINT handler

lock = Lock()
seq = Value("i", 0)
def _worker_signal_handler_and_lock_(*args):
  signal.signal(signal.SIGINT, _signal_handler_)
  #signal.signal(signal.SIGINT, signal.SIG_IGN)
  global seq, lock
  seq, lock = args
  

#Read host.list
try:
  HOST_FILE = open(sys.argv[1])
except:
  print "!! cmd <host_list_file> "
  sys.exit(0)

#Initialize log file
log_f = open(log_file, 'w')
log_f.write(time.strftime("%Y-%m-%d %H:%M")+"\n\n")
log_f.close()

def _write_log(result,result_1):
  log_f = open(log_file, 'a')
  log_f.write("\n".join(result)+"".join(result_1)+"\n")
  log_f.close()

def _close_log():
  log_f = open(log_file, 'a')
  log_f.write("\n\n"+time.strftime("%Y-%m-%d %H:%M")+"\n\n")
  log_f.close()

#Host file parser
HOST_LIST = []
with HOST_FILE as H_L:
  for HOST in H_L:
    #print HOST
    if '#' in HOST: #remove comments
      continue
    elif re.search(r'^[\s]', HOST): #remove ws
      continue
    elif re.search('(\w+\s\w+)', HOST): #remove blanks
      continue
    else:
      #print "Host: "+HOST[:-1] #strip \n
      HOST_LIST.append(HOST.rstrip(os.linesep))
      #print "Host: "+HOST.rstrip(os.linesep) #strip \n
      #break

#print HOST_LIST

# Send notifications
def _notify_(HOST, Notification):
  try:
    notify = smtplib.SMTP('localhost')
    #notify.set_debuglevel(1)
    notify.sendmail('wi-notify@open.net' , 'himirar@gmail.com' ,"Subject: !!"+Notification+", Host:"+HOST )
  except:
    print "Notification failure !!"
  finally:
    notify.quit()

# Test for OpenDNS
def _test_open_dns_(_HOST):
  NS = _HOST
  #print "Name server: "+NS
  _res = dns.resolver.Resolver()
  _res.nameservers = [NS]
  _res.timeout = 2
  _res.lifetime = 1
  try:
    _res.query(Query)
    print "Name Resolved"
    _notify_(NS, "Open DNS")
    return ": Name Resolved, Open DNS"
  except:
    print "Name Resolution Failed"
    return  ": Name Resolution Failed"

# Test for openDNS and openRelay
#def _test_open_relay_((HOSTS, mp_lock)):
def _test_open_relay_(HOSTS):
  Out = []
  #for HOST in HOSTS:
  #print mp_lock
  HOST=HOSTS
  Out_DNS = _test_open_dns_(HOST)
  print "-----------------------------\n"+"".join(HOST.split()) #hostname without spaces
  time.sleep(1)
  socket.setdefaulttimeout(3)
  try:
    smtp = smtplib.SMTP()
    try:
      smtp.connect("".join(HOST.split()))
    except:
      print "Connection failure"
      with lock:
        seq.value += 1
        Out.append( str(seq.value)+": "+HOST+" : Connection failure" )
        _write_log(Out, Out_DNS)
      return (Out, Out_DNS)
    smtp.sendmail('open-relay@openrelay.net' , 'test@yahoo.com' ,'Subject: Open Relay')
    seq.value += 1
    Out.append( str(seq.value)+": "+HOST+" :Open Relay" )
    #Notify admin
    _notify_(HOST, 'Open Mail Relay')
    print "___!!! Open Relay !!!____"

  except smtplib.SMTPRecipientsRefused:
    print "Relay Denied"
    seq.value += 1
    Out.append( str(seq.value)+": "+HOST+" :Relay Denied" )

  except Exception:
    print "SMTP Error"
    seq.value += 1
    Out.append( str(seq.value)+": "+HOST+" :SMTP Error" )
    pass

  else:
    if smtp:
      smtp.quit()
  with lock:
    _write_log(Out, Out_DNS)
  return (Out, Out_DNS)


# Multiprocess initializer
def __mp__():
  workers = Pool(processess, _worker_signal_handler_and_lock_, (seq, lock))
  try:
    #worker_out = workers.map(_test_open_relay_,  zip(HOST_LIST, repeat(mp_lock))) #Multiple args with zip/repeat
    #worker_out = workers.map_async(_test_open_relay_,  HOST_LIST)
    worker_out = workers.imap_unordered(_test_open_relay_,  HOST_LIST)
    #worker_out = workers.imap(_test_open_relay_,  HOST_LIST)
    time.sleep(1)
    workers.close()
    workers.join()
    return  worker_out

  except KeyboardInterrupt:
    print "Keyboard Interrupted"
    workers.terminate()
    workers.join()

# Main
if __name__ == "__main__":
  #prOut = _test_open_relay_(HOST_LIST)
  prOut = __mp__()
  print '\n'.join((map(str,prOut)))
  #__mp__()
  _close_log()
  sys.exit(0)

