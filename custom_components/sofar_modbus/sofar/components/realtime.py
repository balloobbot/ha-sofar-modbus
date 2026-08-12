"""Generated from plugin_sofar.py @ 27875b3b by scripts/generate_sofar_model.py.

Do not hand-edit — re-run the generator instead. See scripts/generate_sofar_model.py
for the translation rules.
"""

from __future__ import annotations

from modbus_connection.model import Component, gauge, integer, string, uint32


class RealtimeData(Component):
    """209 fields, generated — see module docstring."""

    system_state = integer(1028, signed=False)  # 0x0404, allowedtypes=HYBRID | PV
    fault_1 = integer(1029, signed=False)  # 0x0405, allowedtypes=HYBRID | PV
    fault_2 = integer(1030, signed=False)  # 0x0406, allowedtypes=HYBRID | PV
    fault_3 = integer(1031, signed=False)  # 0x0407, allowedtypes=HYBRID | PV
    fault_4 = integer(1032, signed=False)  # 0x0408, allowedtypes=HYBRID | PV
    fault_5 = integer(1033, signed=False)  # 0x0409, allowedtypes=HYBRID | PV
    fault_6 = integer(1034, signed=False)  # 0x040A, allowedtypes=HYBRID | PV
    fault_7 = integer(1035, signed=False)  # 0x040B, allowedtypes=HYBRID | PV
    fault_8 = integer(1036, signed=False)  # 0x040C, allowedtypes=HYBRID | PV
    fault_9 = integer(1037, signed=False)  # 0x040D, allowedtypes=HYBRID | PV
    fault_10 = integer(1038, signed=False)  # 0x040E, allowedtypes=HYBRID | PV
    fault_11 = integer(1039, signed=False)  # 0x040F, allowedtypes=HYBRID | PV
    fault_12 = integer(1040, signed=False)  # 0x0410, allowedtypes=HYBRID | PV
    waiting_time = integer(1047, signed=True)  # 0x0417, allowedtypes=HYBRID | PV
    inverter_temperature_1 = integer(1048, signed=True)  # 0x0418, allowedtypes=HYBRID | PV
    inverter_temperature_2 = integer(1049, signed=True)  # 0x0419, allowedtypes=HYBRID | PV
    heatsink_temperature_1 = integer(1050, signed=True)  # 0x041A, allowedtypes=HYBRID | PV
    heatsink_temperature_2 = integer(1051, signed=True)  # 0x041B, allowedtypes=HYBRID | PV
    module_temperature_1 = integer(1056, signed=True)  # 0x0420, allowedtypes=HYBRID | PV
    module_temperature_2 = integer(1057, signed=True)  # 0x0421, allowedtypes=HYBRID | PV
    serial_number = string(1093, 7)  # 0x0445, allowedtypes=HYBRID | PV
    hardware_version = string(1101, 2)  # 0x044D, allowedtypes=HYBRID | PV
    software_version = string(1103, 4)  # 0x044F, allowedtypes=HYBRID | PV
    grid_frequency = gauge(1156, 0.01, signed=False)  # 0x0484, allowedtypes=HYBRID | PV
    active_power_output_total = gauge(1157, 0.01, signed=True)  # 0x0485, allowedtypes=HYBRID | PV
    reactive_power_output_total = gauge(1158, 0.01, signed=True)  # 0x0486, allowedtypes=HYBRID | PV
    apparent_power_output_total = gauge(1159, 0.01, signed=True)  # 0x0487, allowedtypes=HYBRID | PV
    active_power_pcc_total = gauge(1160, 0.01, signed=True)  # 0x0488, allowedtypes=HYBRID | PV
    reactive_power_pcc_total = gauge(1161, 0.01, signed=True)  # 0x0489, allowedtypes=HYBRID | PV
    apparent_power_pcc_total = gauge(1162, 0.01, signed=True)  # 0x048A, allowedtypes=HYBRID | PV
    voltage_l1 = gauge(1165, 0.1, signed=False)  # 0x048D, allowedtypes=HYBRID | PV
    current_output_l1 = gauge(1166, 0.01, signed=False)  # 0x048E, allowedtypes=HYBRID | PV
    active_power_output_l1 = gauge(1167, 0.01, signed=True)  # 0x048F, allowedtypes=HYBRID | PV
    reactive_power_output_l1 = gauge(1168, 0.01, signed=True)  # 0x0490, allowedtypes=HYBRID | PV
    power_factor_output_l1 = gauge(1169, 0.001, signed=True)  # 0x0491, allowedtypes=HYBRID | PV
    current_pcc_l1 = gauge(1170, 0.01, signed=False)  # 0x0492, allowedtypes=HYBRID | PV
    active_power_pcc_l1 = gauge(1171, 0.01, signed=True)  # 0x0493, allowedtypes=HYBRID | PV
    reactive_power_pcc_l1 = gauge(1172, 0.01, signed=True)  # 0x0494, allowedtypes=HYBRID | PV
    power_factor_pcc_l1 = gauge(1173, 0.001, signed=True)  # 0x0495, allowedtypes=HYBRID | PV
    voltage_l2 = gauge(1176, 0.1, signed=False)  # 0x0498, allowedtypes=HYBRID | PV
    current_output_l2 = gauge(1177, 0.01, signed=False)  # 0x0499, allowedtypes=HYBRID | PV
    active_power_output_l2 = gauge(1178, 0.01, signed=True)  # 0x049A, allowedtypes=HYBRID | PV
    reactive_power_output_l2 = gauge(1179, 0.01, signed=True)  # 0x049B, allowedtypes=HYBRID | PV
    power_factor_output_l2 = gauge(1180, 0.001, signed=True)  # 0x049C, allowedtypes=HYBRID | PV
    current_pcc_l2 = gauge(1181, 0.01, signed=False)  # 0x049D, allowedtypes=HYBRID | PV
    active_power_pcc_l2 = gauge(1182, 0.01, signed=True)  # 0x049E, allowedtypes=HYBRID | PV
    reactive_power_pcc_l2 = gauge(1183, 0.01, signed=True)  # 0x049F, allowedtypes=HYBRID | PV
    power_factor_pcc_l2 = gauge(1184, 0.001, signed=True)  # 0x04A0, allowedtypes=HYBRID | PV
    voltage_l3 = gauge(1187, 0.1, signed=False)  # 0x04A3, allowedtypes=HYBRID | PV
    current_output_l3 = gauge(1188, 0.01, signed=False)  # 0x04A4, allowedtypes=HYBRID | PV
    active_power_output_l3 = gauge(1189, 0.01, signed=True)  # 0x04A5, allowedtypes=HYBRID | PV
    reactive_power_output_l3 = gauge(1190, 0.01, signed=True)  # 0x04A6, allowedtypes=HYBRID | PV
    power_factor_output_l3 = gauge(1191, 0.001, signed=True)  # 0x04A7, allowedtypes=HYBRID | PV
    current_pcc_l3 = gauge(1192, 0.01, signed=False)  # 0x04A8, allowedtypes=HYBRID | PV
    active_power_pcc_l3 = gauge(1193, 0.01, signed=True)  # 0x04A9, allowedtypes=HYBRID | PV
    reactive_power_pcc_l3 = gauge(1194, 0.01, signed=True)  # 0x04AA, allowedtypes=HYBRID | PV
    power_factor_pcc_l3 = gauge(1195, 0.001, signed=True)  # 0x04AB, allowedtypes=HYBRID | PV
    active_power_pv_ext = gauge(1198, 0.01, signed=False)  # 0x04AE, allowedtypes=HYBRID | PV
    active_power_load_sys = gauge(1199, 0.01, signed=False)  # 0x04AF, allowedtypes=HYBRID | PV
    voltage_phase_l1n = gauge(1200, 0.1, signed=False)  # 0x04B0, allowedtypes=HYBRID | PV
    current_output_l1n = gauge(1201, 0.01, signed=False)  # 0x04B1, allowedtypes=HYBRID | PV
    active_power_output_l1n = gauge(1202, 0.01, signed=True)  # 0x04B2, allowedtypes=HYBRID | PV
    current_pcc_l1n = gauge(1203, 0.01, signed=False)  # 0x04B3, allowedtypes=HYBRID | PV
    active_power_pcc_l1n = gauge(1204, 0.01, signed=True)  # 0x04B4, allowedtypes=HYBRID | PV
    voltage_phase_l2n = gauge(1205, 0.1, signed=False)  # 0x04B5, allowedtypes=HYBRID | PV
    current_output_l2n = gauge(1206, 0.01, signed=False)  # 0x04B6, allowedtypes=HYBRID | PV
    active_power_output_l2n = gauge(1207, 0.01, signed=True)  # 0x04B7, allowedtypes=HYBRID | PV
    current_pcc_l2n = gauge(1208, 0.01, signed=False)  # 0x04B8, allowedtypes=HYBRID | PV
    active_power_pcc_l2n = gauge(1209, 0.01, signed=True)  # 0x04B9, allowedtypes=HYBRID | PV
    voltage_line_l1 = gauge(1210, 0.1, signed=False)  # 0x04BA, allowedtypes=HYBRID | PV
    voltage_line_l2 = gauge(1211, 0.1, signed=False)  # 0x04BB, allowedtypes=HYBRID | PV
    voltage_line_l3 = gauge(1212, 0.1, signed=False)  # 0x04BC, allowedtypes=HYBRID | PV
    active_power_offgrid_total = gauge(1284, 0.01, signed=True)  # 0x0504, allowedtypes=HYBRID | EPS
    reactive_power_offgrid_total = gauge(1285, 0.01, signed=True)  # 0x0505, allowedtypes=HYBRID | EPS
    apparent_power_offgrid_total = gauge(1286, 0.01, signed=True)  # 0x0506, allowedtypes=HYBRID | EPS
    offgrid_frequency = gauge(1287, 0.01, signed=False)  # 0x0507, allowedtypes=HYBRID | EPS
    offgrid_voltage = gauge(1290, 0.1, signed=False)  # 0x050A, allowedtypes=HYBRID | X1 | EPS
    offgrid_voltage_l1 = gauge(1290, 0.1, signed=False)  # 0x050A, allowedtypes=HYBRID | X3 | EPS
    offgrid_current_output = gauge(1291, 0.01, signed=True)  # 0x050B, allowedtypes=HYBRID | X1 | EPS
    offgrid_current_output_l1 = gauge(1291, 0.01, signed=True)  # 0x050B, allowedtypes=HYBRID | X3 | EPS
    offgrid_active_power_output = gauge(1292, 0.01, signed=True)  # 0x050C, allowedtypes=HYBRID | X1 | EPS
    offgrid_active_power_output_l1 = gauge(1292, 0.01, signed=True)  # 0x050C, allowedtypes=HYBRID | X3 | EPS
    offgrid_reactive_power_output = gauge(1293, 0.01, signed=True)  # 0x050D, allowedtypes=HYBRID | X1 | EPS
    offgrid_reactive_power_output_l1 = gauge(1293, 0.01, signed=True)  # 0x050D, allowedtypes=HYBRID | X3 | EPS
    offgrid_apparent_power_output = gauge(1294, 0.01, signed=True)  # 0x050E, allowedtypes=HYBRID | X1 | EPS
    offgrid_apparent_power_output_l1 = gauge(1294, 0.01, signed=True)  # 0x050E, allowedtypes=HYBRID | X3 | EPS
    offgrid_loadpeakratio = gauge(1295, 0.01, signed=False)  # 0x050F, allowedtypes=HYBRID | X1 | EPS
    offgrid_loadpeakratio_l1 = gauge(1295, 0.01, signed=False)  # 0x050F, allowedtypes=HYBRID | X3 | EPS
    offgrid_voltage_l2 = gauge(1298, 0.1, signed=False)  # 0x0512, allowedtypes=HYBRID | X3 | EPS
    offgrid_current_output_l2 = gauge(1299, 0.01, signed=True)  # 0x0513, allowedtypes=HYBRID | X3 | EPS
    offgrid_active_power_output_l2 = gauge(1300, 0.01, signed=True)  # 0x0514, allowedtypes=HYBRID | X3 | EPS
    offgrid_reactive_power_output_l2 = gauge(1301, 0.01, signed=True)  # 0x0515, allowedtypes=HYBRID | X3 | EPS
    offgrid_apparent_power_output_l2 = gauge(1302, 0.01, signed=True)  # 0x0516, allowedtypes=HYBRID | X3 | EPS
    offgrid_loadpeakratio_l2 = gauge(1303, 0.01, signed=False)  # 0x0517, allowedtypes=HYBRID | X3 | EPS
    offgrid_voltage_l3 = gauge(1306, 0.1, signed=False)  # 0x051A, allowedtypes=HYBRID | X3 | EPS
    offgrid_current_output_l3 = gauge(1307, 0.01, signed=True)  # 0x051B, allowedtypes=HYBRID | X3 | EPS
    offgrid_active_power_output_l3 = gauge(1308, 0.01, signed=True)  # 0x051C, allowedtypes=HYBRID | X3 | EPS
    offgrid_reactive_power_output_l3 = gauge(1309, 0.01, signed=True)  # 0x051D, allowedtypes=HYBRID | X3 | EPS
    offgrid_apparent_power_output_l3 = gauge(1310, 0.01, signed=True)  # 0x051E, allowedtypes=HYBRID | X3 | EPS
    offgrid_loadpeakratio_l3 = gauge(1311, 0.01, signed=False)  # 0x051F, allowedtypes=HYBRID | X3 | EPS
    offgrid_voltage_output_l1n = gauge(1314, 0.1, signed=False)  # 0x0522, allowedtypes=HYBRID | X3 | EPS
    offgrid_current_output_l1n = gauge(1315, 0.01, signed=True)  # 0x0523, allowedtypes=HYBRID | X3 | EPS
    offgrid_active_power_output_l1n = gauge(1316, 0.01, signed=True)  # 0x0524, allowedtypes=HYBRID | X3 | EPS
    offgrid_voltage_output_l2n = gauge(1317, 0.1, signed=False)  # 0x0525, allowedtypes=HYBRID | X3 | EPS
    offgrid_current_output_l2n = gauge(1318, 0.01, signed=True)  # 0x0526, allowedtypes=HYBRID | X3 | EPS
    offgrid_active_power_output_l2n = gauge(1319, 0.01, signed=True)  # 0x0527, allowedtypes=HYBRID | X3 | EPS
    pv_voltage_1 = gauge(1412, 0.1, signed=False)  # 0x0584, allowedtypes=HYBRID | PV | GEN
    pv_current_1 = gauge(1413, 0.01, signed=False)  # 0x0585, allowedtypes=HYBRID | PV | GEN
    pv_power_1 = gauge(1414, 0.01, signed=False)  # 0x0586, allowedtypes=HYBRID | PV | GEN
    pv_voltage_2 = gauge(1415, 0.1, signed=False)  # 0x0587, allowedtypes=HYBRID | PV | GEN
    pv_current_2 = gauge(1416, 0.01, signed=False)  # 0x0588, allowedtypes=HYBRID | PV | GEN
    pv_power_2 = gauge(1417, 0.01, signed=False)  # 0x0589, allowedtypes=HYBRID | PV | GEN
    pv_voltage_3 = gauge(1418, 0.1, signed=False)  # 0x058A, allowedtypes=HYBRID | PV | GEN | ALL_MPPT_GROUP
    pv_current_3 = gauge(1419, 0.01, signed=False)  # 0x058B, allowedtypes=HYBRID | PV | GEN | ALL_MPPT_GROUP
    pv_power_3 = gauge(1420, 0.01, signed=False)  # 0x058C, allowedtypes=HYBRID | PV | GEN | ALL_MPPT_GROUP
    pv_voltage_4 = gauge(1421, 0.1, signed=False)  # 0x058D, allowedtypes=HYBRID | PV | GEN | MPPT4 | MPPT6 | MPPT8 | MPPT10
    pv_current_4 = gauge(1422, 0.01, signed=False)  # 0x058E, allowedtypes=HYBRID | PV | GEN | MPPT4 | MPPT6 | MPPT8 | MPPT10
    pv_power_4 = gauge(1423, 0.01, signed=False)  # 0x058F, allowedtypes=HYBRID | PV | GEN | MPPT4 | MPPT6 | MPPT8 | MPPT10
    pv_voltage_5 = gauge(1424, 0.1, signed=False)  # 0x0590, allowedtypes=HYBRID | PV | GEN | MPPT6 | MPPT8 | MPPT10
    pv_current_5 = gauge(1425, 0.01, signed=False)  # 0x0591, allowedtypes=HYBRID | PV | GEN | MPPT6 | MPPT8 | MPPT10
    pv_power_5 = gauge(1426, 0.01, signed=False)  # 0x0592, allowedtypes=HYBRID | PV | GEN | MPPT6 | MPPT8 | MPPT10
    pv_voltage_6 = gauge(1427, 0.1, signed=False)  # 0x0593, allowedtypes=HYBRID | PV | GEN | MPPT6 | MPPT8 | MPPT10
    pv_current_6 = gauge(1428, 0.01, signed=False)  # 0x0594, allowedtypes=HYBRID | PV | GEN | MPPT6 | MPPT8 | MPPT10
    pv_power_6 = gauge(1428, 0.01, signed=False)  # 0x0594, allowedtypes=HYBRID | PV | GEN | MPPT6 | MPPT8 | MPPT10
    pv_voltage_7 = gauge(1430, 0.1, signed=False)  # 0x0596, allowedtypes=HYBRID | PV | GEN | MPPT8 | MPPT10
    pv_current_7 = gauge(1431, 0.01, signed=False)  # 0x0597, allowedtypes=HYBRID | PV | GEN | MPPT8 | MPPT10
    pv_power_7 = gauge(1432, 0.01, signed=False)  # 0x0598, allowedtypes=HYBRID | PV | GEN | MPPT8 | MPPT10
    pv_voltage_8 = gauge(1433, 0.1, signed=False)  # 0x0599, allowedtypes=HYBRID | PV | GEN | MPPT8 | MPPT10
    pv_current_8 = gauge(1434, 0.01, signed=False)  # 0x059A, allowedtypes=HYBRID | PV | GEN | MPPT8 | MPPT10
    pv_power_8 = gauge(1435, 0.01, signed=False)  # 0x059B, allowedtypes=HYBRID | PV | GEN | MPPT8 | MPPT10
    pv_voltage_9 = gauge(1436, 0.1, signed=False)  # 0x059C, allowedtypes=HYBRID | PV | GEN | MPPT10
    pv_current_9 = gauge(1437, 0.01, signed=False)  # 0x059D, allowedtypes=HYBRID | PV | GEN | MPPT10
    pv_power_9 = gauge(1438, 0.01, signed=False)  # 0x059E, allowedtypes=HYBRID | PV | GEN | MPPT10
    pv_voltage_10 = gauge(1439, 0.1, signed=False)  # 0x059F, allowedtypes=HYBRID | PV | GEN | MPPT10
    pv_current_10 = gauge(1440, 0.01, signed=False)  # 0x05A0, allowedtypes=HYBRID | PV | GEN | MPPT10
    pv_power_10 = gauge(1441, 0.01, signed=False)  # 0x05A1, allowedtypes=HYBRID | PV | GEN | MPPT10
    pv_power_total = gauge(1476, 0.1, signed=False)  # 0x05C4, allowedtypes=HYBRID | PV | GEN
    battery_voltage_1 = gauge(1540, 0.1, signed=False)  # 0x0604, allowedtypes=HYBRID
    battery_current_1 = gauge(1541, 0.01, signed=True)  # 0x0605, allowedtypes=HYBRID
    battery_power_1 = gauge(1542, 0.01, signed=True)  # 0x0606, allowedtypes=HYBRID
    battery_temperature_1 = integer(1543, signed=True)  # 0x0607, allowedtypes=HYBRID
    battery_capacity_1 = integer(1544, signed=False)  # 0x0608, allowedtypes=HYBRID
    battery_state_of_health_1 = integer(1545, signed=False)  # 0x0609, allowedtypes=HYBRID
    battery_charge_cycle_1 = integer(1546, signed=False)  # 0x060A, allowedtypes=HYBRID
    battery_voltage_2 = gauge(1547, 0.1, signed=False)  # 0x060B, allowedtypes=HYBRID
    battery_current_2 = gauge(1548, 0.01, signed=True)  # 0x060C, allowedtypes=HYBRID
    battery_power_2 = gauge(1549, 0.01, signed=True)  # 0x060D, allowedtypes=HYBRID
    battery_temperature_2 = integer(1550, signed=True)  # 0x060E, allowedtypes=HYBRID
    battery_capacity_2 = integer(1551, signed=False)  # 0x060F, allowedtypes=HYBRID
    battery_state_of_health_2 = integer(1552, signed=False)  # 0x0610, allowedtypes=HYBRID
    battery_charge_cycle_2 = integer(1553, signed=False)  # 0x0611, allowedtypes=HYBRID
    battery_voltage_3 = gauge(1554, 0.1, signed=False)  # 0x0612, allowedtypes=HYBRID | GEN
    battery_current_3 = gauge(1555, 0.01, signed=True)  # 0x0613, allowedtypes=HYBRID | GEN
    battery_power_3 = gauge(1556, 0.01, signed=True)  # 0x0614, allowedtypes=HYBRID | GEN
    battery_temperature_3 = integer(1557, signed=True)  # 0x0615, allowedtypes=HYBRID | GEN
    battery_capacity_3 = integer(1558, signed=False)  # 0x0616, allowedtypes=HYBRID | GEN
    battery_state_of_health_3 = integer(1559, signed=False)  # 0x0617, allowedtypes=HYBRID | GEN
    battery_charge_cycle_3 = integer(1560, signed=False)  # 0x0618, allowedtypes=HYBRID | GEN
    battery_voltage_4 = gauge(1561, 0.1, signed=False)  # 0x0619, allowedtypes=HYBRID | GEN
    battery_current_4 = gauge(1562, 0.01, signed=True)  # 0x061A, allowedtypes=HYBRID | GEN
    battery_power_4 = gauge(1563, 0.01, signed=True)  # 0x061B, allowedtypes=HYBRID | GEN
    battery_temperature_4 = integer(1564, signed=True)  # 0x061C, allowedtypes=HYBRID | GEN
    battery_capacity_4 = integer(1565, signed=False)  # 0x061D, allowedtypes=HYBRID | GEN
    battery_state_of_health_4 = integer(1566, signed=False)  # 0x061E, allowedtypes=HYBRID | GEN
    battery_charge_cycle_4 = integer(1567, signed=False)  # 0x061F, allowedtypes=HYBRID | GEN
    battery_voltage_5 = gauge(1568, 0.1, signed=False)  # 0x0620, allowedtypes=HYBRID | GEN
    battery_current_5 = gauge(1569, 0.01, signed=True)  # 0x0621, allowedtypes=HYBRID | GEN
    battery_power_5 = gauge(1570, 0.01, signed=True)  # 0x0622, allowedtypes=HYBRID | GEN
    battery_temperature_5 = integer(1571, signed=True)  # 0x0623, allowedtypes=HYBRID | GEN
    battery_capacity_5 = integer(1572, signed=False)  # 0x0624, allowedtypes=HYBRID | GEN
    battery_state_of_health_5 = integer(1573, signed=False)  # 0x0625, allowedtypes=HYBRID | GEN
    battery_charge_cycle_5 = integer(1574, signed=False)  # 0x0626, allowedtypes=HYBRID | GEN
    battery_voltage_6 = gauge(1575, 0.1, signed=False)  # 0x0627, allowedtypes=HYBRID | GEN
    battery_current_6 = gauge(1576, 0.01, signed=True)  # 0x0628, allowedtypes=HYBRID | GEN
    battery_power_6 = gauge(1577, 0.01, signed=True)  # 0x0629, allowedtypes=HYBRID | GEN
    battery_temperature_6 = integer(1578, signed=True)  # 0x062A, allowedtypes=HYBRID | GEN
    battery_capacity_6 = integer(1579, signed=False)  # 0x062B, allowedtypes=HYBRID | GEN
    battery_state_of_health_6 = integer(1580, signed=False)  # 0x062C, allowedtypes=HYBRID | GEN
    battery_charge_cycle_6 = integer(1581, signed=False)  # 0x062D, allowedtypes=HYBRID | GEN
    battery_voltage_7 = gauge(1582, 0.1, signed=False)  # 0x062E, allowedtypes=HYBRID | GEN
    battery_current_7 = gauge(1583, 0.01, signed=True)  # 0x062F, allowedtypes=HYBRID | GEN
    battery_power_7 = gauge(1584, 0.01, signed=True)  # 0x0630, allowedtypes=HYBRID | GEN
    battery_temperature_7 = integer(1585, signed=True)  # 0x0631, allowedtypes=HYBRID | GEN
    battery_capacity_7 = integer(1586, signed=False)  # 0x0632, allowedtypes=HYBRID | GEN
    battery_state_of_health_7 = integer(1587, signed=False)  # 0x0633, allowedtypes=HYBRID | GEN
    battery_charge_cycle_7 = integer(1588, signed=False)  # 0x0634, allowedtypes=HYBRID | GEN
    battery_voltage_8 = gauge(1589, 0.1, signed=False)  # 0x0635, allowedtypes=HYBRID | GEN
    battery_current_8 = gauge(1590, 0.01, signed=True)  # 0x0636, allowedtypes=HYBRID | GEN
    battery_power_8 = gauge(1591, 0.01, signed=True)  # 0x0637, allowedtypes=HYBRID | GEN
    battery_temperature_8 = integer(1592, signed=True)  # 0x0638, allowedtypes=HYBRID | GEN
    battery_capacity_8 = integer(1593, signed=False)  # 0x0639, allowedtypes=HYBRID | GEN
    battery_state_of_health_8 = integer(1594, signed=False)  # 0x063A, allowedtypes=HYBRID | GEN
    battery_charge_cycle_8 = integer(1595, signed=False)  # 0x063B, allowedtypes=HYBRID | GEN
    battery_power_total = gauge(1639, 0.1, signed=True)  # 0x0667, allowedtypes=HYBRID
    battery_capacity_total = integer(1640, signed=False)  # 0x0668, allowedtypes=HYBRID
    battery_state_of_health_total = integer(1641, signed=False)  # 0x0669, allowedtypes=HYBRID
    solar_generation_today = uint32(1668, scale=0.01)  # 0x0684, allowedtypes=HYBRID | PV
    solar_generation_total = uint32(1670, scale=0.1)  # 0x0686, allowedtypes=HYBRID | PV
    load_consumption_today = uint32(1672, scale=0.01)  # 0x0688, allowedtypes=HYBRID | PV
    load_consumption_total = uint32(1674, scale=0.1)  # 0x068A, allowedtypes=HYBRID | PV
    import_energy_today = uint32(1676, scale=0.01)  # 0x068C, allowedtypes=HYBRID | PV
    import_energy_total = uint32(1678, scale=0.1)  # 0x068E, allowedtypes=HYBRID | PV
    export_energy_today = uint32(1680, scale=0.01)  # 0x0690, allowedtypes=HYBRID | PV
    export_energy_total = uint32(1682, scale=0.1)  # 0x0692, allowedtypes=HYBRID | PV
    battery_input_energy_today = uint32(1684, scale=0.01)  # 0x0694, allowedtypes=HYBRID
    battery_input_energy_total = uint32(1686, scale=0.1)  # 0x0696, allowedtypes=HYBRID
    battery_output_energy_today = uint32(1688, scale=0.01)  # 0x0698, allowedtypes=HYBRID
    battery_output_energy_total = uint32(1690, scale=0.1)  # 0x069A, allowedtypes=HYBRID

    # rtc: REGISTER_WORDS(6) — y/m/d/h/mi/s, one register each
    _rtc_year = integer(1068, signed=False)
    _rtc_month = integer(1069, signed=False)
    _rtc_day = integer(1070, signed=False)
    _rtc_hour = integer(1071, signed=False)
    _rtc_minute = integer(1072, signed=False)
    _rtc_second = integer(1073, signed=False)

    @property
    def rtc(self) -> str | None:
        """Inverter RTC as "DD/MM/YY HH:MM:SS", or None if unreadable."""
        parts = (self._rtc_day, self._rtc_month, self._rtc_year, self._rtc_hour, self._rtc_minute, self._rtc_second)
        if any(p is None for p in parts):
            return None
        d, mo, y, h, mi, s = parts
        return f"{d:02}/{mo:02}/{y % 100:02} {h:02}:{mi:02}:{s:02}"
