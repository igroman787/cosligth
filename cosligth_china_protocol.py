# Данный код предназначен для работы с АКБ, в котором используется китайские мозги.
# Данный код был написан для работы по самопальному китайскому протоколу - хуй знает что за протокол, но точно не modbus и не can.
# Данный код был написан в командировке за чужим ноутом в течение двух суток.
# Данный код работает напрямую с интерфейсом и общается с АКБ побайтово. Полученные данные на целостность не проверяются - верификация по checksum не реализована.
# Самопальный китайский протокол не способен работать с батареями разных версий в одной сети rs485 - будет наложение двух пакетов друг на друга.

import time
import serial

serialAddress = "/dev/ttyRS485-2"

def CreateSerial(inputPort):
	ser = serial.Serial(
		port=inputPort,
		baudrate=19200,
		parity=serial.PARITY_NONE,
		stopbits=serial.STOPBITS_ONE,
		bytesize=serial.EIGHTBITS,
		timeout=1
	)
	ser.isOpen()
	return ser
#end define

def CloseSerial(ser):
	ser.close()
#end define

def WriteHexToSerial(ser, inputHex):
	inputHex = inputHex.replace(' ', '')
	outputBytes = bytes.fromhex(inputHex)
	hexGroup = HexToGroup(inputHex)
	inputLength = len(hexGroup)
	hexGroupString = ' '.join(hexGroup)
	print("sending[" + str(inputLength) + "]: " + hexGroupString)
	ser.write(outputBytes)
#end define

def ReadHexFromSerial(ser):
	buffer = b''
	# let wait half a second before reading output (let give device time to answer)
	time.sleep(0.5)
	while ser.inWaiting() > 0:
		buffer += ser.read(1)
	if buffer != '':
		bufferHex = buffer.hex()
		bufferHexGroup = HexToGroup(bufferHex)
		bufferLength = len(bufferHexGroup)
		bufferHexGroupString = ' '.join(bufferHexGroup)
		print("getting[" + str(bufferLength) + "]: " + bufferHexGroupString)
	return bufferHexGroupString
#end define

def grouper(iterable, n):
	args = [iter(iterable)] * n
	return zip(*args)
#end define

def HexToGroup(inputHex):
	return [''.join(i) for i in grouper(inputHex, 2)]
#end define

def StringToHex(inputString):
	bytes = inputString.encode("utf-8")
	outputHex = bytes.hex()
	return outputHex
#end define

def HexToString(inputHex):
	inputBytes = bytes.fromhex(inputHex)
	outputString = inputBytes.decode("utf-8")
	return outputString
#end define

def HexToInt(inputHex):
	inputString = HexToString(inputHex)
	outputInt = int(inputString, 16)
	return outputInt
#end define

def GetChecksum(inputHex):
	inputHex = inputHex.replace(' ', '')
	hexGroup = HexToGroup(inputHex)
	sum = 0
	for item in hexGroup:
		sum += int(item, 16)
	checksumBuffer = 65536 - sum
	checksumHex = hex(checksumBuffer)[2:]
	checksumList = list(checksumHex)
	checksum = ''
	for item in checksumList:
		checksum += StringToHex(item)
	return checksum
#end define

def GenerateOutputHex(versionString, addressString, controlCode2String):
	startbit = '7e'
	version = StringToHex(versionString)
	address = StringToHex(addressString)
	controlCode1 = '44 30'
	controlCode2 = StringToHex(controlCode2String)
	length = '45 30 30 32'
	data = '30 31'
	checksum = GetChecksum(version + address + controlCode1 + controlCode2 + length + data)
	stopbit = '0d'
	outputHex = startbit + version + address + controlCode1 + controlCode2 + length + data + checksum + stopbit
	outputHex = outputHex.replace(' ','')
	outputHex = HexToGroup(outputHex)
	outputHex = ' '.join(outputHex)
	return outputHex
#end define

def DecodeInputHex(inputHex, controlCode2):
	inputHex = inputHex.replace(' ', '')
	hexGroup = HexToGroup(inputHex)
	startbit = hexGroup[0]
	versionHex = ''.join(hexGroup[1:3])
	version = HexToString(versionHex)
	addressHex = ''.join(hexGroup[3:5])
	address = HexToString(addressHex)
	controlCode1 = hexGroup[5:7]
	rtn = hexGroup[7:9]
	if (rtn[1]=='31'):
		raise IOError("VER error")
	if (rtn[1]=='32'):
		raise IOError("CHKSUM error")
	if (rtn[1]=='33'):
		raise IOError("LCHKSUM error")
	if (rtn[1]=='34'):
		raise IOError("CID2 invalid")
	if (rtn[1]=='35'):
		raise IOError("command format error")
	if (rtn[1]=='36'):
		raise IOError("invalid data")
	lengthHex = ''.join(hexGroup[9:13])
	lengthBytes = bytes.fromhex(lengthHex)
	length = lengthBytes.decode("utf-8")
	if (version == "21"):
		iterations = 1
		china_indent = 0
	elif (version == "11"):
		iterations = 7
		china_indent = 8 # Лишний отступ полезной информации в байтах, если старая версия - говяный китайский протокол
	indent = 0
	outputArray = dict()
	for i in range(iterations):
		if (controlCode2 == "82"):
			bufferArray = DecodeAnalogInputHex(hexGroup, i)
		elif (controlCode2 == "83"):
			bufferArray = DecodeStatusInputHex(hexGroup, i, china_indent)
		batteryId = bufferArray["batteryId"]
		outputArray.update({str(batteryId):bufferArray})
	return outputArray
#end define

def DecodeAnalogInputHex(hexGroup, i):
	usefulLength = 40 # Длина части пакета в байтах, который содержит нужную нам информацию
	indent = usefulLength*i
	timestamp = int(time.time())
	maxCellVoltHex = ''.join(hexGroup[13+indent:17+indent]) # Максимальное напряжение элемента батареи, В
	maxCellVolt = HexToInt(maxCellVoltHex)/1000
	minCellVoltHex = ''.join(hexGroup[17+indent:21+indent]) # Минимальное напряжение элемента батареи, В
	minCellVolt = HexToInt(minCellVoltHex)/1000
	maxCellTempHex = ''.join(hexGroup[21+indent:23+indent]) # Максимальная температура элемента батареи, °C
	maxCellTemp = HexToInt(maxCellTempHex)
	minCellTempHex = ''.join(hexGroup[23+indent:25+indent]) # Минимальная температура элемента батареи, °C
	minCellTemp = HexToInt(minCellTempHex)
	batteryVoltHex = ''.join(hexGroup[25+indent:29+indent]) # Общее напряжение батареи, В
	batteryVolt = HexToInt(batteryVoltHex)/100
	chargingCurrentHex = ''.join(hexGroup[29+indent:33+indent]) # Ток заряда, А
	chargingCurrent = HexToInt(chargingCurrentHex)/100
	dischargingCurrentHex = ''.join(hexGroup[33+indent:37+indent]) # Ток разряд, А
	dischargingCurrent = HexToInt(dischargingCurrentHex)/100
	SOCHex = ''.join(hexGroup[37+indent:39+indent]) # Уровень заряда, %
	SOC = HexToInt(SOCHex)
	capacityHex = ''.join(hexGroup[39+indent:43+indent]) # Номинальная емкость, Ah
	capacity = HexToInt(capacityHex)/100
	backupTimeHex = ''.join(hexGroup[43+indent:45+indent]) # Оставшееся время резерва, Ч
	backupTime = HexToInt(backupTimeHex)/10
	chargingCurrentLimitHex = ''.join(hexGroup[45+indent:49+indent]) # Лимит тока заряда, А
	chargingCurrentLimit = HexToInt(chargingCurrentLimitHex)/100
	SOHHex = ''.join(hexGroup[49+indent:51+indent]) # Емкость батареи, %
	SOH = HexToInt(SOHHex)
	batteryIdHex = ''.join(hexGroup[51+indent:53+indent]) # Номер батареи
	batteryId = HexToInt(batteryIdHex)
	outputArray = {
		"timestamp":timestamp,
		"maxCellVolt":maxCellVolt,
		"minCellVolt":minCellVolt,
		"maxCellTemp":maxCellTemp,
		"minCellTemp":minCellTemp,
		"batteryVolt":batteryVolt,
		"chargingCurrent":chargingCurrent,
		"dischargingCurrent":dischargingCurrent,
		"SOC":SOC,
		"capacity":capacity,
		"backupTime":backupTime,
		"chargingCurrentLimit":chargingCurrentLimit,
		"SOH":SOH,
		"batteryId":batteryId
	}
	checksum = ''.join(hexGroup[53+indent:57+indent])
	stopbit = ''.join(hexGroup[57+indent])
	return outputArray
#end define

def DecodeStatusInputHex(hexGroup, i, china_indent):
	usefulLength = 34 # Длина части пакета в байтах, который содержит нужную нам информацию
	indent = usefulLength*i + china_indent
	timestamp = int(time.time())
	w1Hex = ''.join(hexGroup[13+indent:17+indent]) # Cell over-voltage warning
	w1 = HexToInt(w1Hex)
	w2Hex = ''.join(hexGroup[17+indent:21+indent]) # Cell under-voltage warning
	w2 = HexToInt(w2Hex)
	w3Hex = ''.join(hexGroup[21+indent:23+indent]) # Charging over-temperature warning
	w3 = HexToInt(w3Hex)
	w4Hex = ''.join(hexGroup[23+indent:25+indent]) # Discharging over-temperature warning
	w4 = HexToInt(w4Hex)
	w5Hex = ''.join(hexGroup[25+indent:27+indent]) # Charging under-temperature warning
	w5 = HexToInt(w5Hex)
	w6Hex = ''.join(hexGroup[27+indent:31+indent]) # Cell over-voltage protection
	w6 = HexToInt(w6Hex)
	w7Hex = ''.join(hexGroup[31+indent:35+indent]) # Cell under-voltage protection
	w7 = HexToInt(w7Hex)
	w8Hex = ''.join(hexGroup[35+indent:37+indent]) # Charging over-temperature protection
	w8 = HexToInt(w8Hex)
	w9Hex = ''.join(hexGroup[37+indent:39+indent]) # Discharging over-temperature protection
	w9 = HexToInt(w9Hex)
	w10Hex = ''.join(hexGroup[39+indent:41+indent]) # Charging under-temperature protection
	w10 = HexToInt(w10Hex)
	w11Hex = ''.join(hexGroup[41+indent:45+indent]) # Working
	w11 = HexToInt(w10Hex)
	batteryIdHex = ''.join(hexGroup[45+indent:47+indent]) # Номер батареи
	batteryId = HexToInt(batteryIdHex)
	outputArray = {
		"timestamp":timestamp,
		"w1":w1,
		"w2":w2,
		"w3":w3,
		"w4":w4,
		"w5":w5,
		"w6":w6,
		"w7":w7,
		"w8":w8,
		"w9":w9,
		"w10":w10,
		"w11":w11,
		"batteryId":batteryId
	}
	checksum = ''.join(hexGroup[47+indent:51+indent])
	stopbit = ''.join(hexGroup[51+indent])
	return outputArray
#end define

def GetAnalogData():
	# Открываем порт для передачи данных
	ser = CreateSerial(serialAddress)
	
	# Формируем, отправляем и принимаем пакеты информации
	controlCode2 = "82" # controlCode2=82||83
	outputHex = GenerateOutputHex("21", "01", controlCode2) # version=11||21, address=01, controlCode2=82||83
	WriteHexToSerial(ser, outputHex)
	inputHex = ReadHexFromSerial(ser)
	outputArray = DecodeInputHex(inputHex, controlCode2)
	
	# Закрываем порт
	CloseSerial(ser)
	
	return outputArray
#end define

def GetStatusData():
	# Открываем порт для передачи данных
	ser = CreateSerial(serialAddress)
	
	# Формируем, отправляем и принимаем пакеты информации
	controlCode2 = "83" # controlCode2=82||83
	outputHex = GenerateOutputHex("21", "01", controlCode2) # version=11||21, address=01, controlCode2=82||83
	WriteHexToSerial(ser, outputHex)
	inputHex = ReadHexFromSerial(ser)
	outputArray = DecodeInputHex(inputHex, controlCode2)
	
	# Закрываем порт
	CloseSerial(ser)
	
	return outputArray
#end define

def DisableBattery():
	ser = CreateSerial(serialAddress)
	outputHex = '7e 32 31 30 31 44 30 34 35 45 30 30 32 32 46 46 44 31 30 0d'
	WriteHexToSerial(ser, outputHex)
	inputHex = ReadHexFromSerial(ser)
	CloseSerial(ser)
	print("Battery disabled.")
#end define

###
### Start of the program
###

# Использование: GetAnalogData() или GetStatusData() или DisableBattery()
data = GetAnalogData()
print("data:")
print(data)


# Примеры посылок:
#root@DESKTOP-QTI81VE:/home/user# python3 test.py
#sending[20]: 7e 32 31 30 31 44 30 38 32 45 30 30 32 30 31 66 64 32 36 0d
#getting[298]: 7e 31 31 30 31 44 30 30 30 36 31 31 38 30 44 30 37 30 43 46 39 32 31 31 41 31 33 38 31 30 30 30 30 30 30 30 30 36 33 31 44 34 43 36 34 30 45 41 36 36 34 30 31 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 32 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 33 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 34 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 35 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 36 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 37 43 38 31 39 0d
#data:
#{'1': {'timestamp': 1554460630, 'maxCellVolt': 3.335, 'minCellVolt': 3.321, 'maxCellTemp': 33, 'minCellTemp': 26, 'batteryVolt': 49.93, 'chargingCurrent': 0.0, 'dischargingCurrent': 0.0, 'SOC': 99, 'capacity': 75.0, 'backupTime': 10.0, 'chargingCurrentLimit': 37.5, 'SOH': 100, 'batteryId': 1}, '2': {'timestamp': 1554460630, 'maxCellVolt': 0.0, 'minCellVolt': 0.0, 'maxCellTemp': 0, 'minCellTemp': 0, 'batteryVolt': 0.0, 'chargingCurrent': 0.0, 'dischargingCurrent': 0.0, 'SOC': 0, 'capacity': 0.0, 'backupTime': 0.0, 'chargingCurrentLimit': 0.0, 'SOH': 0, 'batteryId': 2}, '3': {'timestamp': 1554460630, 'maxCellVolt': 0.0, 'minCellVolt': 0.0, 'maxCellTemp': 0, 'minCellTemp': 0, 'batteryVolt': 0.0, 'chargingCurrent': 0.0, 'dischargingCurrent': 0.0, 'SOC': 0, 'capacity': 0.0, 'backupTime': 0.0, 'chargingCurrentLimit': 0.0, 'SOH': 0, 'batteryId': 3}, '4': {'timestamp': 1554460630, 'maxCellVolt': 0.0, 'minCellVolt': 0.0, 'maxCellTemp': 0, 'minCellTemp': 0, 'batteryVolt': 0.0, 'chargingCurrent': 0.0, 'dischargingCurrent': 0.0, 'SOC': 0, 'capacity': 0.0, 'backupTime': 0.0, 'chargingCurrentLimit': 0.0, 'SOH': 0, 'batteryId': 4}, '5': {'timestamp': 1554460630, 'maxCellVolt': 0.0, 'minCellVolt': 0.0, 'maxCellTemp': 0, 'minCellTemp': 0, 'batteryVolt': 0.0, 'chargingCurrent': 0.0, 'dischargingCurrent': 0.0, 'SOC': 0, 'capacity': 0.0, 'backupTime': 0.0, 'chargingCurrentLimit': 0.0, 'SOH': 0, 'batteryId': 5}, '6': {'timestamp': 1554460630, 'maxCellVolt': 0.0, 'minCellVolt': 0.0, 'maxCellTemp': 0, 'minCellTemp': 0, 'batteryVolt': 0.0, 'chargingCurrent': 0.0, 'dischargingCurrent': 0.0, 'SOC': 0, 'capacity': 0.0, 'backupTime': 0.0, 'chargingCurrentLimit': 0.0, 'SOH': 0, 'batteryId': 6}, '7': {'timestamp': 1554460630, 'maxCellVolt': 0.0, 'minCellVolt': 0.0, 'maxCellTemp': 0, 'minCellTemp': 0, 'batteryVolt': 0.0, 'chargingCurrent': 0.0, 'dischargingCurrent': 0.0, 'SOC': 0, 'capacity': 0.0, 'backupTime': 0.0, 'chargingCurrentLimit': 0.0, 'SOH': 0, 'batteryId': 7}}
#root@DESKTOP-QTI81VE:/home/user# python3 test.py
#sending[20]: 7e 32 31 30 31 44 30 38 33 45 30 30 32 30 31 66 64 32 35 0d
#getting[264]: 7e 31 31 30 31 44 30 30 30 42 30 46 36 30 31 30 30 37 45 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 31 38 30 31 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 32 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 33 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 34 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 35 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 36 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 37 43 46 31 39 0d
#data:
#{'1': {'timestamp': 1554460646, 'w1': 0, 'w2': 0, 'w3': 0, 'w4': 0, 'w5': 0, 'w6': 0, 'w7': 0, 'w8': 0, 'w9': 0, 'w10': 0, 'w11': 0, 'batteryId': 1}, '2': {'timestamp': 1554460646, 'w1': 0, 'w2': 0, 'w3': 0, 'w4': 0, 'w5': 0, 'w6': 0, 'w7': 0, 'w8': 0, 'w9': 0, 'w10': 0, 'w11': 0, 'batteryId': 2}, '3': {'timestamp': 1554460646, 'w1': 0, 'w2': 0, 'w3': 0, 'w4': 0, 'w5': 0, 'w6': 0, 'w7': 0, 'w8': 0, 'w9': 0, 'w10': 0, 'w11': 0, 'batteryId': 3}, '4': {'timestamp': 1554460646, 'w1': 0, 'w2': 0, 'w3': 0, 'w4': 0, 'w5': 0, 'w6': 0, 'w7': 0, 'w8': 0, 'w9': 0, 'w10': 0, 'w11': 0, 'batteryId': 4}, '5': {'timestamp': 1554460646, 'w1': 0, 'w2': 0, 'w3': 0, 'w4': 0, 'w5': 0, 'w6': 0, 'w7': 0, 'w8': 0, 'w9': 0, 'w10': 0, 'w11': 0, 'batteryId': 5}, '6': {'timestamp': 1554460646, 'w1': 0, 'w2': 0, 'w3': 0, 'w4': 0, 'w5': 0, 'w6': 0, 'w7': 0, 'w8': 0, 'w9': 0, 'w10': 0, 'w11': 0, 'batteryId': 6}, '7': {'timestamp': 1554460646, 'w1': 0, 'w2': 0, 'w3': 0, 'w4': 0, 'w5': 0, 'w6': 0, 'w7': 0, 'w8': 0, 'w9': 0, 'w10': 0, 'w11': 0, 'batteryId': 7}}
#root@DESKTOP-QTI81VE:/home/user# python3 test.py
#sending[20]: 7e 32 31 30 31 44 30 38 32 45 30 30 32 30 31 66 64 32 36 0d
#getting[58]: 7e 32 31 30 31 44 30 30 30 36 30 32 38 30 44 30 41 30 44 30 33 31 41 31 41 31 33 38 38 30 30 30 30 30 30 30 30 35 41 32 37 31 30 36 34 30 37 44 30 36 34 30 31 46 35 35 34 0d
#data:
#{'1': {'timestamp': 1554460668, 'maxCellVolt': 3.338, 'minCellVolt': 3.331, 'maxCellTemp': 26, 'minCellTemp': 26, 'batteryVolt': 50.0, 'chargingCurrent': 0.0, 'dischargingCurrent': 0.0, 'SOC': 90, 'capacity': 100.0, 'backupTime': 10.0, 'chargingCurrentLimit': 20.0, 'SOH': 100, 'batteryId': 1}}
#root@DESKTOP-QTI81VE:/home/user# python3 test.py
#sending[20]: 7e 32 31 30 31 44 30 38 33 45 30 30 32 30 31 66 64 32 35 0d
#getting[52]: 7e 32 31 30 31 44 30 30 30 43 30 32 32 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 31 38 30 31 46 37 32 37 0d
#data:
#{'1': {'timestamp': 1554460690, 'w1': 0, 'w2': 0, 'w3': 0, 'w4': 0, 'w5': 0, 'w6': 0, 'w7': 0, 'w8': 0, 'w9': 0, 'w10': 0, 'w11': 0, 'batteryId': 1}}
#root@DESKTOP-QTI81VE:/home/user#
