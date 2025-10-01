// 전역 변수
let db = null;
let isDbLoaded = false;
let csColumns = [];
let csData = [];
let fontColumns = [];
let fontData = [];

let isFixedLayout = true; // true = 고정형 레이아웃, false = 동적 레이아웃(센서 4개 이상일 경우)
let eventSource = null;
let isConnected = false;
let dataCount = 0;
let activeSensors = new Set();
let SENSOR_CONFIGS = {};
let SERVER_URL = localStorage.getItem("serverUrl") || "http://127.0.0.1:5002";
let API_KEY = localStorage.getItem("apiKey") || "sensor-monitor-key-2024";

// DOM 요소
const gridDom = document.getElementById("sensor-cards");
const fixedDom = document.getElementById("fixed-layout");
const dynamicDom = document.getElementById("dynamic-layout");

// SQL.js 초기화
async function initSQLite() {
  try {
    const sqlite = await initSqlJs({
      locateFile: (file) =>
        `https://cdnjs.cloudflare.com/ajax/libs/sql.js/1.8.0/${file}`,
    });
    window.sqlite = sqlite;
    addToLog("SQL.js 초기화 완료", "success");
  } catch (error) {
    addToLog("SQL.js 초기화 실패: " + error.message, "error");
  }
}

// 로컬 데이터베이스 파일 로드
async function loadLocalDatabase() {
  if (!window.sqlite) {
    addToLog(
      "SQL.js가 아직 초기화되지 않았습니다. 잠시 기다려주세요.",
      "error"
    );
    return false;
  }

  try {
    addToLog("로컬 sensor.db 파일 로딩 중...", "info");

    const response = await fetch("./sensor.db");
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    const arrayBuffer = await response.arrayBuffer();
    db = new window.sqlite.Database(new Uint8Array(arrayBuffer));
    isDbLoaded = true;

    addToLog("데이터베이스 로드 완료: sensor.db", "success");

    // CS 테이블 데이터 로드
    await loadCSTableData("cs", "ORDER BY idx ASC LIMIT 10");

    // Font 테이블 데이터 로드
    await loadCSTableData("font_set");

    return true;
  } catch (error) {
    addToLog("데이터베이스 로드 실패: " + error.message, "error");
    console.error("데이터베이스 로드 오류:", error);
    return false;
  }
}

// CS 테이블 데이터 로드
async function loadCSTableData(tableName, queryOption) {
  try {
    // 테이블 존재 확인
    if (!isTableExists(tableName)) {
      addToLog(`${tableName} 테이블이 존재하지 않습니다.`, "warning");
      return;
    }

    // 테이블 정보 및 데이터 로드
    const tableInfo = await getTableInfo(tableName);
    const tableData = await getTableData(tableName, queryOption);

    if (tableName === "cs") {
      // 전역 변수에 저장
      csColumns = tableInfo;
      csData = tableData;
    } else if (tableName === "font_set") {
      // 전역 변수에 저장
      fontColumns = tableInfo;
      fontData = processFontData(tableData);
    }

    addToLog(
      `${tableName} 테이블 데이터 로드 완료 (${tableData.length}개 행)`,
      "success"
    );
  } catch (error) {
    console.error(`${tableName} 테이블 데이터 로드 오류:`, error);
    addToLog(`${tableName} 테이블 데이터 로드 실패: ${error.message}`, "error");
  }
}

// 테이블 존재 여부 확인
function isTableExists(tableName) {
  try {
    const result = db.exec(
      `SELECT name FROM sqlite_master WHERE type='table' AND name='${tableName}';`
    );
    return result.length > 0 && result[0].values.length > 0;
  } catch (error) {
    console.error(`테이블 존재 확인 오류 (${tableName}):`, error);
    return false;
  }
}

// 테이블 컬럼 정보 조회
function getTableInfo(tableName) {
  try {
    const result = db.exec(`PRAGMA table_info(${tableName});`);
    if (result.length > 0) {
      return result[0].values.map((row) => row[1]); // 컬럼명만 추출
    }
    return [];
  } catch (error) {
    console.error(`테이블 정보 조회 오류 (${tableName}):`, error);
    return [];
  }
}

// 테이블 데이터 조회 및 변환
function getTableData(tableName, queryOption) {
  try {
    const query = `SELECT * FROM ${tableName} ${queryOption};`;
    const result = db.exec(query);

    if (result.length > 0) {
      const rawData = result[0];
      return rawData.values.map((row) => {
        const obj = {};
        rawData.columns.forEach((column, index) => {
          obj[column] = row[index];
        });
        return obj;
      });
    }
    return [];
  } catch (error) {
    console.error(`테이블 데이터 조회 오류 (${tableName}):`, error);
    return [];
  }
}

// font_set 테이블 데이터를 getDeviceFontOption 포맷에 맞게 가공
function processFontData(rawFontData) {
  const processedData = {};

  rawFontData.forEach((fontItem) => {
    const fcode = fontItem.fcode;

    if (!processedData[fcode]) {
      processedData[fcode] = {
        id: fcode,
        options: [],
      };
    }

    // 폰트 옵션 객체 생성
    const option = {
      id: fontItem.fname,
      value: fontItem.ftext || "",
      fontSize: parseInt(fontItem.fsize || 24),
      fontName: fontItem.ffont || fontItem.fontName || "굴림",
      fontWeight: fontItem.fstyle || "Normal",
      fontColor: fontItem.fcolor || "White",
      bgColor: fontItem.fbg || "Transparent",
    };

    processedData[fcode].options.push(option);
  });

  return processedData;
}

// 설정 로드
function loadSettings() {
  document.getElementById("serverUrl").value = SERVER_URL;
  document.getElementById("apiKey").value = API_KEY;
}

// 설정 표시
function showSettings() {
  // loadSettings();
  const modal = new bootstrap.Modal(document.getElementById("settingsModal"));
  modal.show();
}

// 설정 저장
function saveSettings() {
  SERVER_URL = document.getElementById("serverUrl").value;
  API_KEY = document.getElementById("apiKey").value;

  localStorage.setItem("serverUrl", SERVER_URL);
  localStorage.setItem("apiKey", API_KEY);

  const modal = bootstrap.Modal.getInstance(
    document.getElementById("settingsModal")
  );
  modal.hide();

  addToLog("[시스템] 설정이 저장되었습니다.", "info");
}

// 연결 토글 함수
function toggleConnection() {
  if (isConnected) {
    disconnectSSE();
  } else {
    connectSSE();
  }
}

// SSE 연결
async function connectSSE() {
  // 이미 연결된 EventSource가 있으면 중복 연결 방지
  if (eventSource && Array.isArray(eventSource) && eventSource.length > 0) {
    addToLog(
      "[경고] 이미 SSE 연결이 존재합니다. 중복 연결을 방지합니다.",
      "warning"
    );
    return;
  }

  // cs 테이블에서 use="Y"인 모든 장비 찾기
  const activeDevices = csData.filter((item) => item.use === "Y");

  // monitor 컬럼 값으로 정렬 (monitor1, monitor2 순서)
  activeDevices.sort((a, b) => {
    const aMonitor = a.monitor || "";
    const bMonitor = b.monitor || "";

    // monitor1, monitor2 형태에서 숫자 부분 추출
    const aNum = parseInt(aMonitor.replace(/\D/g, "")) || 0;
    const bNum = parseInt(bMonitor.replace(/\D/g, "")) || 0;

    return aNum - bNum; // 오름차순 정렬 (1, 2, 3...)
  });

  if (activeDevices.length === 0) {
    addToLog(
      "[경고] 활성화된 장비가 없습니다. cs 테이블을 확인하세요.",
      "warning"
    );
    return;
  }

  if (!API_KEY) {
    addToLog(
      "[오류] API 키가 설정되지 않았습니다. 설정을 확인하세요.",
      "danger"
    );
    return;
  }

  addToLog(
    `[연결] ${activeDevices.length}개 장비에 SSE 연결 시도 중...`,
    "info"
  );

  // 각 활성 장비에 대해 SSE 연결 생성
  activeDevices.forEach((device, index) => {
    const deviceUrl = `http://${device.ip}:${device.port}`;
    const monitorName = device.monitor || `monitor${index + 1}`;

    addToLog(`[연결] ${monitorName} (${device.ip}:${device.port})`, "info");

    try {
      // 각 장비별로 EventSource 생성
      const deviceEventSource = new EventSource(
        `${deviceUrl}/api/public-sensor-stream?api_key=${encodeURIComponent(
          API_KEY
        )}`
      );

      // 장비별 연결 상태 이벤트 핸들러
      deviceEventSource.onopen = () => {
        addToLog(
          `[성공] ${monitorName} (${device.ip}:${device.port}) SSE 연결됨`,
          "success"
        );

        // 첫 번째 장비 연결 성공 시 전역 상태 업데이트
        if (index === 0) {
          isConnected = true;
          addToLog(
            "[성공] 첫 번째 장비 연결 성공, 시스템 준비 완료",
            "success"
          );
        }
      };

      deviceEventSource.onmessage = (event) => {
        // 장비 정보를 메시지에 추가하여 구분
        const messageWithDevice = {
          data: event.data,
          deviceInfo: {
            ip: device.ip,
            port: device.port,
            deviceId: device.idx,
            monitor: device.monitor, // monitor 정보 추가
            monitorIndex: index, // monitor 순서 인덱스 추가
          },
        };
        handleMessage(messageWithDevice);
      };

      deviceEventSource.onerror = (error) => {
        console.error(
          `${monitorName} (${device.ip}:${device.port}) SSE 오류:`,
          error
        );
        addToLog(
          `[오류] ${monitorName} (${device.ip}:${device.port}) SSE 연결 오류`,
          "danger"
        );
        deviceEventSource.close();
      };

      // 전역 변수에 EventSource 저장 (배열로 관리)
      if (!Array.isArray(eventSource)) {
        eventSource = [];
      }
      eventSource.push(deviceEventSource);
    } catch (error) {
      addToLog(
        `[오류] ${monitorName} (${device.ip}:${device.port}) 연결 실패: ${error.message}`,
        "danger"
      );
      console.error(
        `${monitorName} (${device.ip}:${device.port}) 연결 오류:`,
        error
      );
    }
  });
}

function addToLog(message, type) {
  console.log(message, type);
}

// 메시지 처리
function handleMessage(event) {
  try {
    // event.data가 존재하는지 확인
    if (!event.data) {
      addToLog("[경고] event.data가 undefined입니다.", "warning");
      return;
    }

    const data = JSON.parse(event.data);

    // 특수 메시지 처리
    if (data.type === "connection") {
      if (data.connected) {
        addToLog("[성공] TCP 서버에 연결되었습니다.", "success");
      } else {
        addToLog("[경고] TCP 서버 연결이 끊어졌습니다.", "warning");
      }
      return;
    }

    if (data.type === "heartbeat") {
      // heartbeat는 로그에 출력하지 않음
      return;
    }
  } catch (e) {
    // JSON이 아닌 경우 센서 데이터로 처리
    const rawData = event.data;

    // rawData가 유효한지 확인
    if (!rawData || rawData.trim() === "") {
      addToLog("[경고] rawData가 비어있거나 유효하지 않습니다.", "warning");
      return;
    }

    // 장비 정보가 있으면 로그에 포함
    const deviceInfo = event.deviceInfo
      ? ` [${event.deviceInfo.monitor || event.deviceInfo.ip}:${
          event.deviceInfo.port
        }]`
      : "";

    // 원본 데이터를 로그에 기록
    addToLog(`[수신${deviceInfo}] ${rawData}`, "info");

    // STX/ETX 제거 후 데이터 처리
    const cleanedData = removeSTXETX(rawData);

    // dvId와 monitorIndex 값 확인
    const dvId = event.deviceInfo ? event.deviceInfo.deviceId : "unknown";
    const monitorIndex = event.deviceInfo ? event.deviceInfo.monitorIndex : 0;

    processData(cleanedData, dvId, monitorIndex);

    dataCount++;
    lastDataTime = Date.now(); // 마지막 데이터 수신 시간 업데이트
  }
}

// SSE 연결 해제
function disconnectSSE() {
  if (eventSource) {
    if (Array.isArray(eventSource)) {
      // 여러 EventSource가 있는 경우 모두 종료
      eventSource.forEach((source, index) => {
        if (source) {
          source.close();
          addToLog(`[종료] 장비 ${index + 1} SSE 연결 종료`, "warning");
        }
      });
    } else {
      // 단일 EventSource인 경우
      eventSource.close();
      addToLog("[종료] SSE 연결이 종료되었습니다.", "warning");
    }
    eventSource = null;
  }

  isConnected = false;
  addToLog("[종료] 모든 SSE 연결이 종료되었습니다.", "warning");
}

// 데이터 처리 함수
function processData(rawData, dvId, monitorIndex) {
  try {
    // rawData 유효성 검사
    if (!rawData || typeof rawData !== "string") {
      addToLog(
        `[경고] processData: rawData가 유효하지 않습니다. (${typeof rawData}) ${rawData}`,
        "warning"
      );
      return;
    }

    const parts = rawData.split("|");

    if (parts.length >= 3) {
      const deviceId = parts[0];
      const sensorType = parts[1]; // PM인 경우 2개의 그리드가 보여져야 하기 때문에 sensorType은 PM25와 PM10 두개로 구분 | GASM인 경우 6개의 그리드가 보여져야 하기 때문에 sensorType은 GASM_O2, GASM_NO2, GASM_CO2, GASM_CO, GASM_CH4, GASM_H2S 6개로 구분
      const location = parts[2];

      // 센서 카드 생성/확인 (monitorIndex 포함)
      // 센서 타입에 따른 그리드 개수 결정
      if (sensorType === "PM") {
        // PM 센서: PM2.5와 PM10 두 개의 그리드 생성
        const pmTypes = ["PM25", "PM10"];
        pmTypes.forEach((pmType, index) => {
          const uniqueSensorId = `${pmType}-${dvId}`;
          if (!activeSensors.has(uniqueSensorId)) {
            ensureSensorCard(pmType, deviceId, location, dvId, monitorIndex);
          }
          // 센서 데이터 업데이트 (PM 타입별로 구분)
          updateSensorData(pmType, deviceId, location, rawData, dvId);
        });
      } else if (sensorType === "GASM") {
        // GASM 센서: 6개의 가스 타입별 그리드 생성
        const gasTypes = [
          "GASM_O2",
          "GASM_NO2",
          "GASM_CO",
          "GASM_CO2",
          "GASM_CH4",
          "GASM_H2S",
        ];
        gasTypes.forEach((gasType, index) => {
          const uniqueSensorId = `${gasType}-${dvId}`;
          if (!activeSensors.has(uniqueSensorId)) {
            ensureSensorCard(gasType, deviceId, location, dvId, monitorIndex);
          }
          // 센서 데이터 업데이트 (가스 타입별로 구분)
          updateSensorData(gasType, deviceId, location, rawData, dvId);
        });
      } else {
        // 기타 센서: 기존 방식대로 1개의 그리드 생성
        ensureSensorCard(sensorType, deviceId, location, dvId, monitorIndex);
        updateSensorData(sensorType, deviceId, location, rawData, dvId);
      }
    } else {
      addToLog(
        `[경고] processData: 데이터 형식이 올바르지 않습니다. parts.length=${parts.length}`,
        "warning"
      );
    }
  } catch (error) {
    console.error("데이터 처리 오류:", error);
    addToLog("[오류] 데이터 처리 실패: " + error.message, "danger");
  }
}

// 모든 장비의 총 센서 개수 계산 함수
function calculateTotalSensorCount() {
  let totalCount = 0;

  // csData에서 활성화된 장비들 확인
  const activeDevices = csData.filter((item) => item.use === "Y");

  activeDevices.forEach((device) => {
    if (device.type === "PM") {
      totalCount += 2; // PM은 PM2.5, PM10 두 개
    } else if (device.type === "GASM") {
      totalCount += 6; // GASM은 6개 가스 타입
    } else {
      totalCount += 1; // 기타 센서는 1개
    }
  });
  return totalCount;
}

// 실제 센서 데이터 기반으로 총 센서 개수 계산 (동적)
function calculateActualSensorCount() {
  // 실제로 데이터가 들어온 센서 타입들을 기반으로 계산
  const sensorTypeCounts = {};

  // activeSensors에서 센서 타입별 개수 계산
  activeSensors.forEach((sensorId) => {
    const sensorType = sensorId.split("-")[0]; // PM25, PM10, GASM_O2 등
    const baseType = sensorType.startsWith("GASM_")
      ? "GASM"
      : sensorType.startsWith("PM")
      ? "PM"
      : sensorType;

    if (!sensorTypeCounts[baseType]) {
      sensorTypeCounts[baseType] = 0;
    }
    sensorTypeCounts[baseType]++;
  });

  let totalCount = 0;
  Object.entries(sensorTypeCounts).forEach(([type, count]) => {
    if (type === "PM") {
      totalCount += count; // PM25, PM10 개별 계산
    } else if (type === "GASM") {
      totalCount += count; // GASM_O2, GASM_NO2 등 개별 계산
    } else {
      totalCount += count; // 기타 센서들
    }
  });

  return totalCount;
}

// 센서 카드를 Dynamic Layout용으로 변환
function convertSensorToDynamicLayout(sensorElement) {
  const cardId = sensorElement.id;
  const sensorType = cardId.split("-")[2]; // sensor-card-PM25-4에서 PM25 추출
  const dvId = cardId.split("-")[3]; // sensor-card-PM25-4에서 4 추출

  // 현재 센서의 데이터 값들 추출
  const dataElement = sensorElement.querySelector(`#${sensorType}-${dvId}-0`);
  const dataValue = dataElement?.textContent || "-";
  const dataColor = dataElement?.style?.color || "#0000FE"; // 현재 색상 유지
  const titleElement = sensorElement.querySelector(".sensor-tit");
  const title = titleElement ? titleElement.textContent : "센서";

  // Dynamic Layout용 간단한 HTML 생성 (색상 정보 포함)
  const dynamicHtml = `
    <div class="sensor-item" id="${cardId}">
      <h2>${title}</h2>
      <span id="${sensorType}-${dvId}-0" style="color: ${setColor(
    dataColor
  )};">${dataValue}</span>
    </div>
  `;

  return dynamicHtml;
}

// 모든 센서 카드를 dynamic-layout으로 이동
function moveAllSensorsToDynamicLayout() {
  const fixedSensors = fixedDom.querySelectorAll(".sensor-item");

  fixedSensors.forEach((sensor) => {
    // 센서 카드를 Dynamic Layout용으로 변환
    const dynamicHtml = convertSensorToDynamicLayout(sensor);

    // 변환된 HTML을 dynamic-layout에 추가
    dynamicDom.insertAdjacentHTML("beforeend", dynamicHtml);
  });

  fixedDom.innerHTML = "";
}

// 센서 카드를 Fixed Layout용으로 변환
function convertSensorToFixedLayout(sensorElement) {
  const cardId = sensorElement.id;
  const sensorType = cardId.split("-")[2]; // sensor-card-PM25-4에서 PM25 추출
  const dvId = cardId.split("-")[3]; // sensor-card-PM25-4에서 4 추출

  // 현재 센서의 데이터 값들 추출
  const dataValue =
    sensorElement.querySelector(`#${sensorType}-${dvId}-0`)?.textContent || "-";
  const titleElement = sensorElement.querySelector("h2");
  const title = titleElement ? titleElement.textContent : "센서";

  // 센서 설정 가져오기
  const config =
    SENSOR_CONFIGS[sensorType] || getDefaultSensorConfig(sensorType);
  const fontOptions = getDeviceFontOption(sensorType);

  if (!fontOptions) {
    console.warn(`${sensorType} 센서의 폰트 옵션을 찾을 수 없습니다.`);
    return null;
  }

  const { title: titleConfig, data, unit, ranges } = fontOptions;

  // Fixed Layout용 상세한 HTML 생성
  let rangeHtml = "";
  let fieldsHtml = "";

  // 범위 설정 값
  ranges
    .filter((range) => range.title && range.title.value !== "")
    .forEach((range, index) => {
      rangeHtml += `
        <div class="range-item range-${index + 1}">
          <div class="range-item-head" style="font-size: ${
            range.title.fontSize
          }px;color: ${setColor(
        range.title.fontColor
      )};background-color: ${setColor(range.title.bgColor)};">${
        range.title.value
      }</div>
          <div class="range-item-value" style="font-size: ${
            range.value.fontSize
          }px;color: ${setColor(
        range.value.fontColor
      )};background-color: ${setColor(range.value.bgColor)};">${
        range.value.value
      }</div>
        </div>
      `;
    });

  // 필드 설정 값
  const visibleFields = config.fields.filter((field) => {
    if (field.visible !== false) {
      if (
        sensorType === "VIBRO" ||
        sensorType === "TILT" ||
        sensorType === "CRACK" ||
        sensorType === "SOUND"
      ) {
        if (field.index !== 0 && field.index !== 4) {
          return field;
        }
        return false;
      } else if (sensorType === "WIND") {
        if (
          field.index === 1 ||
          field.index === 2 ||
          field.index === 3 ||
          field.index === 5
        ) {
          return field;
        }
        return false;
      } else if (sensorType === "PM25" || sensorType === "PM10") {
        if (field.index === 1 || field.index === 2 || field.index === 3) {
          return field;
        }
        return false;
      } else return field;
    }
  });

  visibleFields.forEach((field, index) => {
    const fieldId = `${sensorType}-${dvId}-${field.index}`;
    fieldsHtml += `
      <div class="info-item">
        <h5>${field.name}</h5>
        <span id="${fieldId}">-</span>
      </div>
    `;
  });

  const fixedHtml = `
    <div class="sensor-item" id="${cardId}">
      <div class="sensor-top">
        <div class="sensor-top-tit" style="background: ${setColor(
          titleConfig.bgColor
        )}">
          <span class="sensor-tit" style="font-size: ${
            titleConfig.fontSize
          }px;color: ${setColor(
    titleConfig.fontColor
  )};-webkit-text-stroke-color: ${setColor(
    titleConfig.fontColor
  )};">${title}</span>
          <span class="sensor-format" style="font-size: ${
            unit.fontSize
          }px;color: ${unit.fontColor};">${unit.value}</span>
        </div>
        <div class="sensor-top-value" style="background-color: ${setColor(
          data.bgColor
        )};">
          <span id="${sensorType}-${dvId}-0" style="font-size: ${
    data.fontSize
  }px;color: ${data.fontColor};">${dataValue}</span>
        </div>
      </div>
      <div class="sensor-bottom">
        <div class="sensor-bottom-range">
          ${rangeHtml}
        </div>
        <div class="sensor-bottom-info">
          ${fieldsHtml}
        </div>
      </div>
    </div>
  `;

  return fixedHtml;
}

// 모든 센서 카드를 fixed-layout으로 이동
function moveAllSensorsToFixedLayout() {
  const dynamicSensors = dynamicDom.querySelectorAll(".sensor-item");

  dynamicSensors.forEach((sensor) => {
    // 센서 카드를 Fixed Layout용으로 변환
    const fixedHtml = convertSensorToFixedLayout(sensor);

    if (fixedHtml) {
      // 변환된 HTML을 fixed-layout에 추가
      fixedDom.insertAdjacentHTML("beforeend", fixedHtml);
    }
  });

  dynamicDom.innerHTML = "";
}

// 강제 레이아웃 설정 함수 (테스트용)
function forceLayout(layoutType, sensorCount) {
  if (layoutType === "dynamic") {
    // Fixed Layout에서 Dynamic Layout으로 전환 시 센서 카드 이동
    if (isFixedLayout) {
      moveAllSensorsToDynamicLayout();
    }
    fixedDom.style.display = "none";
    dynamicDom.style.display = "grid";
    isFixedLayout = false;
  } else {
    // Dynamic Layout에서 Fixed Layout으로 전환 시 센서 카드 이동
    if (!isFixedLayout) {
      moveAllSensorsToFixedLayout();
    }
    fixedDom.className = "";
    fixedDom.classList.add("grid-layout");
    fixedDom.classList.add(`grid-${sensorCount}`);

    fixedDom.style.display = "grid";
    dynamicDom.style.display = "none";
    isFixedLayout = true;
    const gridTemplate = `repeat(${sensorCount}, 1fr)`;
    fixedDom.style.gridTemplateColumns = gridTemplate;
  }
}

// Fixed Layout 그리드 컬럼 수 업데이트 함수
function updateFixedLayoutGrid() {
  if (!isFixedLayout) return;

  const currentSensorCount = activeSensors.size;
  const gridTemplate = `repeat(${currentSensorCount}, 1fr)`;

  fixedDom.className = "";
  fixedDom.classList.add("grid-layout");
  fixedDom.classList.add(`grid-${currentSensorCount}`);

  fixedDom.style.gridTemplateColumns = gridTemplate;
}

// 레이아웃 초기 설정 함수
function initializeLayout() {
  // 실제 센서 데이터가 있으면 실제 개수 사용, 없으면 csData 기반 계산
  const actualSensorCount = calculateActualSensorCount();
  const csDataSensorCount = calculateTotalSensorCount();
  const totalSensorCount =
    actualSensorCount > 0 ? actualSensorCount : csDataSensorCount;

  if (totalSensorCount > 4) {
    // 4개 초과 시 dynamic-layout 사용
    forceLayout("dynamic", totalSensorCount);
  } else {
    // 4개 이하 시 fixed-layout 사용
    forceLayout("fixed", totalSensorCount);
  }
}

// 센서 카드 추가/업데이트 함수
function ensureSensorCard(sensorType, deviceId, location, dvId, monitorIndex) {
  // 장비별로 고유한 센서 ID 생성 (센서타입-장비ID)
  const uniqueSensorId = `${sensorType}-${dvId}`;

  if (!activeSensors.has(uniqueSensorId)) {
    activeSensors.add(uniqueSensorId);

    // 첫 번째 센서일 때 대기 메시지 제거 및 레이아웃 초기화
    if (activeSensors.size === 1) {
      document.getElementById("fixed-layout").innerHTML = "";
      document.getElementById("dynamic-layout").innerHTML = "";
      initializeLayout(); // 레이아웃 초기 설정
    }

    // 새 센서 카드 생성 (장비별 고유 ID 포함)
    const cardHtml = createSensorCard(sensorType, deviceId, location, dvId);
    if (cardHtml) {
      // 현재 레이아웃 상태에 따라 적절한 컨테이너에 추가
      const currentView = isFixedLayout ? "fixed-layout" : "dynamic-layout";
      const sensorCardsContainer = document.getElementById(currentView);

      // 센서 카드를 현재 레이아웃에 맞는 컨테이너에 추가
      if (monitorIndex === 0) {
        // 첫 번째 monitor는 맨 앞에 추가
        sensorCardsContainer.insertAdjacentHTML("afterbegin", cardHtml);
      } else {
        // 나머지는 순서대로 추가
        sensorCardsContainer.insertAdjacentHTML("beforeend", cardHtml);
      }

      // 센서 추가 후 레이아웃 재확인
      const currentActualCount = calculateActualSensorCount();

      // 4개 초과로 증가했으면 Dynamic Layout으로 전환
      if (currentActualCount > 4 && isFixedLayout) {
        forceLayout("dynamic", currentActualCount);
      }

      // 레이아웃에 따른 그리드 설정
      if (isFixedLayout) {
        // Fixed Layout인 경우 그리드 컬럼 수 업데이트
        updateFixedLayoutGrid();
      } else {
        // Dynamic Layout인 경우 그리드 설정
        gridSet();
      }

      // 센서 설정이 없으면 기본 설정 생성
      if (!SENSOR_CONFIGS[sensorType]) {
        SENSOR_CONFIGS[sensorType] = getDefaultSensorConfig(sensorType);
      }
    }
  }
}

// 센서 장치 폰트 옵션
function getDeviceFontOption(sensorType) {
  // 데이터베이스에서 가공된 fontData가 있으면 우선 사용
  if (fontData && fontData[sensorType]) {
    const dbConfig = fontData[sensorType];
    return {
      title: dbConfig.options.find(
        (opt) => opt.id.trim().toLowerCase() === "title"
      ),
      data: dbConfig.options.find(
        (opt) => opt.id.trim().toLowerCase() === "data"
      ),
      unit: dbConfig.options.find(
        (opt) => opt.id.trim().toLowerCase() === "unit"
      ),
      ranges: Array.from({ length: 4 }, (_, i) => i).map((curNum) => ({
        title: dbConfig.options.find(
          (opt) => opt.id.trim().toLowerCase() === `checkt${curNum + 1}`
        ),
        value: dbConfig.options.find(
          (opt) => opt.id.trim().toLowerCase() === `checkd${curNum + 1}`
        ),
      })),
      opts: dbConfig.options.filter(
        (opt) =>
          opt.id.trim().toLowerCase() === "avgt" ||
          opt.id.trim().toLowerCase() === "montht" ||
          opt.id.trim().toLowerCase() === "maxt" ||
          opt.id.trim().toLowerCase() === "opt"
      ),
    };
  }

  // 데이터베이스에 없으면 기본 설정 사용
  const defaultOpts = [
    {
      id: "title",
      value: "장비 센서",
      fontSize: 44,
      fontName: "굴림",
      fontWeight: "Bold",
      fontColor: "White",
      bgColor: "43, 56, 143",
    },
    {
      id: "data",
      value: "-",
      fontSize: 200,
      fontName: "DSEG7Classic",
      fontWeight: "Bold",
      fontColor: "0, 0, 254",
      bgColor: "White",
    },
    {
      id: "unit",
      value: "(단위 -)",
      fontSize: 20,
      fontName: "굴림",
      fontWeight: "Bold",
      fontColor: "255, 204, 0",
      bgColor: "43, 56, 143",
    },
    {
      id: "CheckT1",
      value: "좋음",
      fontSize: 24,
      fontName: "굴림",
      fontWeight: "Bold",
      fontColor: "White",
      bgColor: "0, 171, 229",
    },
    {
      id: "CheckT2",
      value: "보통",
      fontSize: 24,
      fontName: "굴림",
      fontWeight: "Bold",
      fontColor: "White",
      bgColor: "137, 197, 81",
    },
    {
      id: "CheckT3",
      value: "나쁨",
      fontSize: 24,
      fontName: "굴림",
      fontWeight: "Bold",
      fontColor: "White",
      bgColor: "253, 188, 28",
    },
    {
      id: "CheckT4",
      value: "매우나쁨",
      fontSize: 24,
      fontName: "굴림",
      fontWeight: "Bold",
      fontColor: "White",
      bgColor: "238, 64, 54",
    },
    {
      id: "CheckD1",
      value: "-",
      fontSize: 24,
      fontName: "굴림",
      fontWeight: "Bold",
      fontColor: "White",
      bgColor: "70, 70, 70",
    },
    {
      id: "CheckD2",
      value: "-",
      fontSize: 24,
      fontName: "굴림",
      fontWeight: "Bold",
      fontColor: "White",
      bgColor: "70, 70, 70",
    },
    {
      id: "CheckD3",
      value: "-",
      fontSize: 24,
      fontName: "굴림",
      fontWeight: "Bold",
      fontColor: "White",
      bgColor: "70, 70, 70",
    },
    {
      id: "CheckD4",
      value: "-",
      fontSize: 24,
      fontName: "굴림",
      fontWeight: "Bold",
      fontColor: "White",
      bgColor: "70, 70, 70",
    },
    {
      id: "MaxT",
      value: "금일 최대",
      fontSize: 24,
      fontName: "굴림",
      fontWeight: "Bold",
      fontColor: "White",
      bgColor: "Transparent",
    },
    {
      id: "AvgT",
      value: "금일 최대",
      fontSize: 24,
      fontName: "굴림",
      fontWeight: "Bold",
      fontColor: "White",
      bgColor: "Transparent",
    },
    {
      id: "MonthT",
      value: "당월 평균",
      fontSize: 24,
      fontName: "굴림",
      fontWeight: "Bold",
      fontColor: "White",
      bgColor: "Transparent",
    },
    {
      id: "OpT",
      value: "",
      fontSize: 24,
      fontName: "굴림",
      fontWeight: "Bold",
      fontColor: "White",
      bgColor: "Transparent",
    },
  ];

  return {
    title: defaultOpts.find((opt) => opt.id === "title"),
    data: defaultOpts.find((opt) => opt.id === "data"),
    unit: defaultOpts.find((opt) => opt.id === "unit"),
    ranges: Array.from({ length: 4 }, (_, i) => i).map((curNum) => ({
      title: defaultOpts.find((opt) => opt.id === `CheckT${curNum + 1}`),
      value: defaultOpts.find((opt) => opt.id === `CheckD${curNum + 1}`),
    })),
    opts: defaultOpts.filter(
      (opt) =>
        opt.id === "AvgT" ||
        opt.id === "MonthT" ||
        opt.id === "MaxT" ||
        opt.id === "OpT"
    ),
  };
}

// 기본 센서 설정 생성
function getDefaultSensorConfig(sensorType) {
  const configs = {
    PM: {
      name: "미세먼지 센서",
      icon: "fas fa-smog",
      color: "primary",
      fields: [
        { index: 0, name: "PM2.5", unit: "㎍/㎥", visible: true },
        { index: 1, name: "PM2.5 MAX", unit: "㎍/㎥", visible: true },
        {
          index: 4,
          name: "PM2.5 상태",
          unit: "",
          visible: true,
          status: true,
        },
        { index: 6, name: "PM10", unit: "㎍/㎥", visible: true },
        { index: 7, name: "PM10 MAX", unit: "㎍/㎥", visible: true },
        {
          index: 10,
          name: "PM10 상태",
          unit: "",
          visible: true,
          status: true,
        },
      ],
    },
    PM25: {
      name: "PM2.5 센서",
      icon: "fas fa-smog",
      color: "primary",
      fields: [
        { index: 0, name: "PM2.5", unit: "㎍/㎥", visible: true },
        { index: 1, name: "금일최대", unit: "㎍/㎥", visible: true },
        { index: 2, name: "금일평균", unit: "㎍/㎥", visible: true },
        { index: 3, name: "당월평균", unit: "㎍/㎥", visible: true },
        { index: 4, name: "예보", unit: "㎍/㎥", visible: true },
        {
          index: 5,
          name: "PM2.5 상태",
          unit: "",
          visible: true,
          status: true,
        },
      ],
    },
    PM10: {
      name: "PM10 센서",
      icon: "fas fa-smog",
      color: "info",
      fields: [
        { index: 0, name: "PM10", unit: "㎍/㎥", visible: true },
        { index: 1, name: "금일최대", unit: "㎍/㎥", visible: true },
        { index: 2, name: "금일평균", unit: "㎍/㎥", visible: true },
        { index: 3, name: "당월평균", unit: "㎍/㎥", visible: true },
        { index: 4, name: "예보", unit: "㎍/㎥", visible: true },
        {
          index: 5,
          name: "PM10 상태",
          unit: "",
          visible: true,
          status: true,
        },
      ],
    },
    SOUND: {
      name: "소음 센서",
      icon: "fas fa-volume-up",
      color: "success",
      fields: [
        { index: 0, name: "현재", unit: "dB", visible: true },
        { index: 1, name: "최대", unit: "dB", visible: true },
        { index: 2, name: "평균", unit: "dB", visible: true },
        { index: 4, name: "상태", unit: "", visible: true, status: true },
      ],
    },
    VIBRO: {
      name: "진동 센서",
      icon: "fas fa-wave-square",
      color: "secondary",
      fields: [
        { index: 0, name: "현재", unit: "mm/s", visible: true },
        { index: 1, name: "최대", unit: "mm/s", visible: true },
        { index: 2, name: "평균", unit: "mm/s", visible: true },
        { index: 4, name: "상태", unit: "", visible: true, status: true },
      ],
    },
    TILT: {
      name: "기울기 센서",
      icon: "fas fa-level-up-alt",
      color: "info",
      fields: [
        { index: 0, name: "현재", unit: "°", visible: true },
        { index: 1, name: "최대", unit: "°", visible: true },
        { index: 2, name: "평균", unit: "°", visible: true },
        { index: 4, name: "상태", unit: "", visible: true, status: true },
      ],
    },
    CRACK: {
      name: "균열 센서",
      icon: "fas fa-bolt",
      color: "warning",
      fields: [
        { index: 0, name: "현재", unit: "mm", visible: true },
        { index: 1, name: "최대", unit: "mm", visible: true },
        { index: 2, name: "평균", unit: "mm", visible: true },
        { index: 4, name: "상태", unit: "", visible: true, status: true },
      ],
    },
    WIND: {
      name: "풍속 센서",
      icon: "fas fa-wind",
      color: "info",
      fields: [
        { index: 0, name: "풍속", unit: "m/s", visible: true },
        { index: 1, name: "최대", unit: "m/s", visible: true },
        { index: 4, name: "상태", unit: "", visible: true, status: true },
        { index: 5, name: "풍향각", unit: "°", visible: true },
        { index: 6, name: "풍향", unit: "", visible: true },
      ],
    },
    O2: {
      name: "산소 센서",
      icon: "fas fa-lungs",
      color: "success",
      fields: [
        { index: 0, name: "산소농도", unit: "%", visible: true },
        { index: 4, name: "최대", unit: "%", visible: true },
        { index: 5, name: "평균", unit: "%", visible: true },
        { index: 7, name: "상태", unit: "", visible: true, status: true },
      ],
    },
    MQ: {
      name: "MQ 센서",
      icon: "fas fa-fire",
      color: "warning",
      fields: [
        { index: 0, name: "LPG", unit: "ppm", visible: true },
        { index: 1, name: "CO", unit: "ppm", visible: true },
        { index: 2, name: "Smoke", unit: "ppm", visible: true },
        {
          index: 6,
          name: "LPG 상태",
          unit: "",
          visible: true,
          status: true,
        },
      ],
    },
    NOX: {
      name: "NOx 센서",
      icon: "fas fa-smog",
      color: "danger",
      fields: [
        { index: 0, name: "NO2", unit: "ppm", visible: true },
        { index: 1, name: "CO", unit: "ppm", visible: true },
        { index: 4, name: "NO2 평균", unit: "ppm", visible: true },
        { index: 5, name: "상태", unit: "", visible: true, status: true },
      ],
    },
    GASM: {
      name: "가스 센서",
      icon: "fas fa-cloud",
      color: "dark",
      fields: [
        { index: 0, name: "가스1", unit: "ppm", visible: true },
        {
          index: 4,
          name: "상태1",
          unit: "",
          visible: true,
          status: true,
        },
        { index: 5, name: "가스2", unit: "ppm", visible: true },
        {
          index: 9,
          name: "상태2",
          unit: "",
          visible: true,
          status: true,
        },
      ],
    },
    GASM_O2: {
      name: "산소 가스 센서",
      icon: "fas fa-lungs",
      color: "success",
      fields: [
        { index: 0, name: "O2", unit: "ppm", visible: true },
        { index: 1, name: "O2 MAX", unit: "ppm", visible: true },
        { index: 2, name: "O2 MIN", unit: "ppm", visible: true },
        { index: 3, name: "O2 AVG", unit: "ppm", visible: true },
        {
          index: 4,
          name: "O2 상태",
          unit: "",
          visible: true,
          status: true,
        },
      ],
    },
    GASM_NO2: {
      name: "이산화질소 가스 센서",
      icon: "fas fa-smog",
      color: "warning",
      fields: [
        { index: 0, name: "NO2", unit: "ppm", visible: true },
        { index: 1, name: "NO2 MAX", unit: "ppm", visible: true },
        { index: 2, name: "NO2 MIN", unit: "ppm", visible: true },
        { index: 3, name: "NO2 AVG", unit: "ppm", visible: true },
        {
          index: 4,
          name: "NO2 상태",
          unit: "",
          visible: true,
          status: true,
        },
      ],
    },
    GASM_CO: {
      name: "일산화탄소 가스 센서",
      icon: "fas fa-smog",
      color: "warning",
      fields: [
        { index: 0, name: "CO", unit: "ppm", visible: true },
        { index: 1, name: "CO MAX", unit: "ppm", visible: true },
        { index: 2, name: "CO MIN", unit: "ppm", visible: true },
        { index: 3, name: "CO AVG", unit: "ppm", visible: true },
        {
          index: 4,
          name: "CO 상태",
          unit: "",
          visible: true,
          status: true,
        },
      ],
    },
    GASM_CO2: {
      name: "이산화탄소 가스 센서",
      icon: "fas fa-smog",
      color: "danger",
      fields: [
        { index: 0, name: "SO2", unit: "ppm", visible: true },
        { index: 1, name: "SO2 MAX", unit: "ppm", visible: true },
        { index: 2, name: "SO2 MIN", unit: "ppm", visible: true },
        { index: 3, name: "SO2 AVG", unit: "ppm", visible: true },
        {
          index: 4,
          name: "SO2 상태",
          unit: "",
          visible: true,
          status: true,
        },
      ],
    },
    GASM_CH4: {
      name: "메탄 가스 센서",
      icon: "fas fa-fire",
      color: "danger",
      fields: [
        { index: 0, name: "CH4", unit: "ppm", visible: true },
        { index: 1, name: "CH4 MAX", unit: "ppm", visible: true },
        { index: 2, name: "CH4 MIN", unit: "ppm", visible: true },
        { index: 3, name: "CH4 AVG", unit: "ppm", visible: true },
        {
          index: 4,
          name: "CH4 상태",
          unit: "",
          visible: true,
          status: true,
        },
      ],
    },
    GASM_H2S: {
      name: "황화수소 가스 센서",
      icon: "fas fa-skull-crossbones",
      color: "danger",
      fields: [
        { index: 0, name: "H2S", unit: "ppm", visible: true },
        { index: 1, name: "H2S MAX", unit: "ppm", visible: true },
        { index: 2, name: "H2S MIN", unit: "ppm", visible: true },
        { index: 3, name: "H2S AVG", unit: "ppm", visible: true },
        {
          index: 4,
          name: "H2S 상태",
          unit: "",
          visible: true,
          status: true,
        },
      ],
    },
  };

  return (
    configs[sensorType] || {
      name: `${sensorType} 센서`,
      icon: "fas fa-microchip",
      color: "secondary",
      fields: [],
    }
  );
}

function setColor(color) {
  return color.split(",").length === 1
    ? color.toLowerCase().trim()
    : `rgb(${color})`;
}

// 동적 센서 카드 생성 함수
function createSensorCard(sensorType, deviceId, location, dvId) {
  const config =
    SENSOR_CONFIGS[sensorType] || getDefaultSensorConfig(sensorType);
  const fontOptions = getDeviceFontOption(sensorType); // 폰트 설정 값

  if (!fontOptions) {
    console.warn(`${sensorType} 센서의 폰트 옵션을 찾을 수 없습니다.`);
    return null;
  }

  const { title, data, unit, ranges, opts } = fontOptions;

  // 장비별 고유한 카드 ID 생성
  const cardId = `sensor-card-${sensorType}-${dvId}`;

  console.log("센서 카드 생성 시작:", cardId);
  console.log("현재 레이아웃 상태:", isFixedLayout ? "Fixed" : "Dynamic");
  console.log("config", config);
  console.log("title", title);
  console.log("data", data);
  console.log("unit", unit);
  console.log("ranges", ranges);
  console.log("opts", opts);

  if (isFixedLayout) {
    let rangeHtml = ""; // 범위 설정 값
    let fieldsHtml = ""; // 필드 설정 값

    ranges
      .filter((range) => range.title && range.title.value !== "")
      .forEach((range, index) => {
        rangeHtml += `
        <div class="range-item range-${index + 1}">
          <div class="range-item-head" style="font-size: ${
            range.title.fontSize
          }px;color: ${setColor(
          range.title.fontColor
        )};background-color: ${setColor(range.title.bgColor)};">${
          range.title.value
        }</div>
          <div class="range-item-value" style="font-size: ${
            range.value.fontSize
          }px;color: ${setColor(
          range.value.fontColor
        )};background-color: ${setColor(range.value.bgColor)};">${
          range.value.value
        }</div>
        </div>
      `;
      });

    // 필드 설정 값
    // const visibleFields = config.fields.filter((field) => {
    //   if (field.visible !== false) {
    //     if (
    //       sensorType === "VIBRO" ||
    //       sensorType === "TILT" ||
    //       sensorType === "CRACK" ||
    //       sensorType === "SOUND"
    //     ) {
    //       if (field.index !== 0 && field.index !== 4) {
    //         return field;
    //       }
    //       return false;
    //     } else if (sensorType === "WIND") {
    //       if (
    //         field.index === 1 ||
    //         field.index === 2 ||
    //         field.index === 3 ||
    //         field.index === 5
    //       ) {
    //         return field;
    //       }
    //       return false;
    //     } else if (sensorType === "PM25" || sensorType === "PM10") {
    //       if (field.index === 1 || field.index === 2 || field.index === 3) {
    //         return field;
    //       }
    //       return false;
    //     } else return field;
    //   }
    // });
    // opts에서 특정 ID들만 필터링하고 value가 빈 문자열이 아닌 것만 선택
    const validOpts = opts.filter((opt) => {
      const validIds = ["MaxT", "AvgT", "MonthT", "OpT"];
      return validIds.includes(opt.id) && opt.value !== "";
    });

    // config.fields와 validOpts를 매핑해서 필드 생성
    validOpts.forEach((fontOption, index) => {
      // config.fields에서 해당하는 필드 찾기 (index + 1 기반, 0번은 메인 값이므로)
      const configField = config.fields.find(
        (field) => field.index === index + 1
      );

      if (!configField) {
        return; // 해당하는 config 필드가 없으면 건너뛰기
      }

      // 장비별 고유한 필드 ID 생성 (configField.index 사용)
      const fieldId = `${sensorType}-${dvId}-${configField.index}`;

      fieldsHtml += `
        <div class="info-item">
          <h5 style="font-size: ${fontOption.fontSize}px;color: ${setColor(
        fontOption.fontColor
      )};">${fontOption.value}</h5>
          <span id="${fieldId}">-</span>
        </div>
      `;
    });

    const cardHtml = `
      <div class="sensor-item" id="${cardId}">
        <div class="sensor-top">
          <div class="sensor-top-tit" style="background: ${setColor(
            title.bgColor
          )}">
            <span class="sensor-tit" style="font-size: ${
              title.fontSize
            }px;color: ${setColor(
      title.fontColor
    )};-webkit-text-stroke-color: ${setColor(title.fontColor)};">${
      title.value
    }</span>
            <span class="sensor-format" style="font-size: ${
              unit.fontSize
            }px;color: ${unit.fontColor};">${unit.value}</span>
          </div>
          <div class="sensor-top-value" style="background-color: ${setColor(
            data.bgColor
          )};">
            <span id="${sensorType}-${dvId}-0" style="font-size: ${
      data.fontSize
    }px;color: ${data.fontColor};">-</span>
          </div>
        </div>
        <div class="sensor-bottom">
          <div class="sensor-bottom-range">
            ${rangeHtml}
          </div>
          <div class="sensor-bottom-info">
            ${fieldsHtml}
          </div>
        </div>
      </div>
    `;

    return cardHtml;
  } else {
    // Dynamic Layout용 간단한 카드
    const cardHtml = `
      <div class="sensor-item" id="${cardId}">
        <h2>${title.value}</h2>
        <span id="${sensorType}-${dvId}-0" style="color: ${data.fontColor};">${data.value}</span>
      </div>
    `;
    return cardHtml;
  }
}

// STX/ETX 제거 함수
function removeSTXETX(data) {
  // 데이터 유효성 검사
  if (!data || typeof data !== "string") {
    return data || "";
  }

  let cleaned = data;

  // STX (0x02) 제거 - 문자열 시작
  if (cleaned.charCodeAt(0) === 0x02 || cleaned.startsWith("\u0002")) {
    cleaned = cleaned.substring(1);
  }

  // ETX (0x03) 제거 - 문자열 끝
  if (
    cleaned.charCodeAt(cleaned.length - 1) === 0x03 ||
    cleaned.endsWith("\u0003")
  ) {
    cleaned = cleaned.substring(0, cleaned.length - 1);
  }

  // 추가적인 제어 문자들 제거
  cleaned = cleaned.replace(/[\x00-\x08\x0E-\x1F\x7F]/g, "");

  const result = cleaned.trim();
  return result;
}

// 센서 데이터 업데이트 함수
function updateSensorData(sensorType, deviceId, location, dataString, dvId) {
  const config =
    SENSOR_CONFIGS[sensorType] || getDefaultSensorConfig(sensorType);

  // 데이터 파싱 및 업데이트
  let dataValues = "";
  let statusmapping = "";
  let dataparse = "";
  let dataparse2 = "";
  let dataparse3 = "";
  let dataparse4 = "";
  let dataparse5 = "";
  let dataparse6 = "";
  let dataparse7 = "";
  let dataparse8 = "";

  const parts1 = dataString.split("^")[0]; // '^127.0.0.1' 부분 제거
  const parts2 = parts1.split("|"); // '|'로 분리

  if (["SOUND", "VIBRO", "TILT", "CRACK"].includes(sensorType)) {
    // SOUND - 1|SOUND||54.1,78.0,55.4,55.4,G^192.168.0.27
    // VIBRO - 1|VIBRO|HWT905|0.2,13.6,0.5,15.4,N^127.0.0.1
    // TILT -  1|TILT|HWT905|0.3,13.6,0.5,15.4,N^127.0.0.1
    // CRACK - 1|CRACK|MINUO|0.1,13.6,0.5,15.4,N^127.0.0.1

    // 54.1, 78.0, 55.4, 55.4, G
    dataparse = parts2.length > 3 ? parts2[3] : "";

    dataValues = dataparse.split(","); // ','로 분리

    // 각 데이터 위치 별, 상태값으로 매핑할 인덱스들 (필요에 따라 수정 가능)
    // -1은 상태값이 없음을 의미
    // 예: index 0,1,2,3은 index 4
    statusmapping = [4, 4, 4, 4, -1];
  } else if (sensorType == "WIND") {
    // WIND - 1|WIND|UltraSonic|4.1,10.2,5.3,5.2,G,200,SE^192.168.0.27

    // 4.1, 10.2, 5.3, 5.2, G, 200, SE
    dataparse = parts2.length > 3 ? parts2[3] : "";

    dataValues = dataparse.split(","); // ','로 분리

    // 각 데이터 위치 별, 상태값으로 매핑할 인덱스들 (필요에 따라 수정 가능)
    // -1은 상태값이 없음을 의미
    // 예: index 0,1,2,3은 index 4
    statusmapping = [4, 4, 4, 4, -1, -1, -1];
  } else if (sensorType == "NOX") {
    // NOX - 1|NOX|NO2|0.022_679,0.044,0.005,0.054,W_W^192.168.0.27
    // 0.022: NO2 메인값, 679: CO(제외), 0.044: 금일최대, 0.005: 금일평균, 0.054: 당월평균

    dataparse = parts2.length > 3 ? parts2[3] : "";

    // '_'와 ','로 분리한 후 CO 값(두 번째 값) 제외
    const allValues = dataparse.split(/[_,]/);
    dataValues = [
      allValues[0], // 0.022 (NO2 메인값)
      allValues[2], // 0.044 (금일최대)
      allValues[3], // 0.005 (금일평균)
      allValues[4], // 0.054 (당월평균)
      allValues[5], // W (상태1)
      allValues[6], // W (상태2)
    ];

    // 각 데이터 위치 별, 상태값으로 매핑할 인덱스들
    // index 0,1,2,3은 index 4의 상태값 참조
    statusmapping = [4, 4, 4, 4, -1, -1];
  } else if (sensorType === "PM25" || sensorType === "PM10") {
    // PM - 1|PM||35,35,18,20,N,0,75,75,37,35,G,0,,,^192.168.0.27

    // 35,35,18,20,N,0,
    // 75,75,37,35,G,0,
    // x,x,x
    if (sensorType === "PM25") {
      dataparse = parts2.length > 3 ? parts2[3] : "";
      dataValues = dataparse.split(",").slice(0, 6); // ','로 분리
    } else if (sensorType === "PM10") {
      dataparse = parts2.length > 3 ? parts2[3] : "";
      dataValues = dataparse.split(",").slice(6, 12); // ','로 분리
    }

    // 상태값 위치 변경 (4번째와 5번째 값 교체)
    const temp = dataValues[4];
    dataValues[4] = dataValues[5];
    dataValues[5] = temp;
    console.log("dataValues222", dataValues);

    // 각 데이터 위치 별, 상태값으로 매핑할 인덱스들 (필요에 따라 수정 가능)
    // -1은 상태값이 없음을 의미
    // PM25/PM10: [0,1,2,3,4,5] -> 상태값은 인덱스 5에 있음 (4번째와 5번째 값 교체 후)
    // 메인 값들(0,1,2,3,4번)은 모두 인덱스 5의 상태값을 참조, 상태 필드(5번)는 -1
    statusmapping = [5, 5, 5, 5, 5, -1];
    // statusmapping = [4, 4, 4, 4, -1, 4, 10, 10, 10, 10, -1, 10, -1, -1, -1];
  } else if (sensorType == "O2") {
    // O2 - 1|O2|PER|19.90_240_30_1200,20.10,19.80,19.86,W|19.90_240_30_1200^192.168.0.27

    // 19.90_240_30_1200,20.10,19.80,19.86,W
    dataparse = parts2.length > 3 ? parts2[3] : "";
    // 19.90_240_30_1200
    dataparse2 = parts2.length > 4 ? parts2[4] : "";

    dataValues = (dataparse + "," + dataparse2).split(/[_,]/); // '_' or ','로 분리

    // 각 데이터 위치 별, 상태값으로 매핑할 인덱스들 (필요에 따라 수정 가능)
    // -1은 상태값이 없음을 의미
    statusmapping = [7, 7, 7, 7, 7, 7, 7, -1, 7, -1, -1, -1];
  } else if (sensorType == "MQ") {
    // MQ - 1|MQ|LPG|40_660_160,0,0,180,N_N_N|40_660_160^192.168.0.27

    // 40_660_160,0,0,180,N_N_N
    dataparse = parts2.length > 3 ? parts2[3] : "";
    // 40_660_160
    dataparse2 = parts2.length > 4 ? parts2[4] : "";

    dataValues = (dataparse + "," + dataparse2).split(/[_,]/); // '_' or ','로 분리

    // 각 데이터 위치 별, 상태값으로 매핑할 인덱스들 (필요에 따라 수정 가능)
    // -1은 상태값이 없음을 의미
    statusmapping = [6, 7, 8, -1, -1, -1, -1, -1, -1, 6, 7, 8];
  } else if (
    sensorType === "GASM_O2" ||
    sensorType === "GASM_NO2" ||
    sensorType === "GASM_CO2" ||
    sensorType === "GASM_CO" ||
    sensorType === "GASM_CH4" ||
    sensorType === "GASM_H2S"
  ) {
    // GASM - 1|GASM|WMKY2000|5.999997,34,16,16,-1|11.99999,70,34,34,-1|18,70,30,30,-1|23.99999,70,34,34,-1|30,70,32,32,-1|36,70,35,35,-1|42.00002,70,33,33,1|47.99997,70,35,35,1^192.168.0.27

    // GASM_O2 - 5.999997,34,16,16,-1
    if (sensorType === "GASM_O2") {
      dataparse = parts2.length > 3 ? parts2[3] : "";
      dataValues = dataparse.split(/[_,]/); // '_' or ','로 분리
    }
    if (sensorType === "GASM_NO2") {
      dataparse = parts2.length > 4 ? parts2[4] : "";
      dataValues = dataparse.split(/[_,]/); // '_' or ','로 분리
    }
    if (sensorType === "GASM_CO") {
      dataparse = parts2.length > 5 ? parts2[5] : "";
      dataValues = dataparse.split(/[_,]/); // '_' or ','로 분리
    }
    if (sensorType === "GASM_CO2") {
      dataparse = parts2.length > 6 ? parts2[6] : "";
      dataValues = dataparse.split(/[_,]/); // '_' or ','로 분리
    }
    if (sensorType === "GASM_CH4") {
      dataparse = parts2.length > 7 ? parts2[7] : "";
      dataValues = dataparse.split(/[_,]/); // '_' or ','로 분리
    }
    if (sensorType === "GASM_H2S") {
      dataparse = parts2.length > 8 ? parts2[8] : "";
      dataValues = dataparse.split(/[_,]/); // '_' or ','로 분리
    }

    // 숫자로 변환 가능한 경우, 소수점 2자리로 포맷팅
    dataValues = dataValues.map((value) => {
      if (!isNaN(value) && !isNaN(parseFloat(value))) {
        return parseFloat(value).toFixed(2);
      }
      return value;
    });

    // 각 데이터 위치 별, 상태값으로 매핑할 인덱스들 (필요에 따라 수정 가능)
    // -1은 상태값이 없음을 의미
    statusmapping = [4, 4, 4, 4, 4];
  }

  console.log("=============");
  console.log("config : ", config);
  console.log("statusmapping", statusmapping);
  console.log("dataValues 33333", dataValues);

  // Dynamic Layout인 경우 메인 값(0번)만 업데이트
  if (!isFixedLayout) {
    const mainFieldId = `${sensorType}-${dvId}-0`;
    const mainElement = document.getElementById(mainFieldId);

    if (mainElement && dataValues[0] !== undefined) {
      const value = dataValues[0].trim();
      mainElement.textContent = value.replaceAll(".", " .") || "--";

      // 상태값에 따른 색상 업데이트
      const statusIndex = statusmapping[0];
      const statusValue =
        statusIndex >= 0 && statusIndex < dataValues.length
          ? dataValues[statusIndex]
          : "X";

      console.log("Dynamic Layout - statusValue:", statusValue);
      console.log("Dynamic Layout - mainElement:", mainElement);
      updateStatusBadge(mainElement, statusValue);
    }
  } else {
    // Fixed Layout인 경우 - 메인 데이터 값(0번) 먼저 업데이트
    const mainFieldId = `${sensorType}-${dvId}-0`;
    const mainElement = document.getElementById(mainFieldId);

    if (mainElement && dataValues[0] !== undefined) {
      const value = dataValues[0].trim();
      mainElement.textContent = value.replaceAll(".", " .") || "--";

      // 메인 값에 상태 색상 적용
      const statusIndex = statusmapping[0];
      const statusValue =
        statusIndex >= 0 && statusIndex < dataValues.length
          ? dataValues[statusIndex]
          : "X";

      console.log("Fixed Layout - 메인 값 업데이트:", value);
      console.log("Fixed Layout - statusValue:", statusValue);
      updateStatusBadge(mainElement, statusValue);
    }

    // 그 다음 opts에서 필터링된 필드들 업데이트
    const fontOptions = getDeviceFontOption(sensorType);
    const { opts } = fontOptions;

    // opts에서 특정 ID들만 필터링하고 value가 빈 문자열이 아닌 것만 선택
    const validOpts = opts.filter((opt) => {
      const validIds = ["MaxT", "AvgT", "MonthT", "OpT"];
      return validIds.includes(opt.id) && opt.value !== "";
    });

    // 실제로 생성된 필드들만 업데이트
    validOpts.forEach((fontOption, index) => {
      // config.fields에서 해당하는 필드 찾기 (index + 1 기반, 0번은 메인 값이므로)
      const configField = config.fields.find(
        (field) => field.index === index + 1
      );

      if (!configField) {
        return; // 해당하는 config 필드가 없으면 건너뛰기
      }

      // 장비별 고유한 필드 ID 생성
      const fieldId = `${sensorType}-${dvId}-${configField.index}`;
      const element = document.getElementById(fieldId);
      console.log("Fixed Layout - 필드 업데이트:", fieldId);

      if (element && dataValues[configField.index] !== undefined) {
        const value = dataValues[configField.index].trim();
        element.textContent = value.replaceAll(".", " .") || "--";
      } else {
        console.warn(`필드를 찾을 수 없거나 데이터가 없음: ${fieldId}`, {
          element: element,
          dataValue: dataValues[configField.index],
          fieldIndex: configField.index,
        });
      }
    });
  }
}

// 값 배지 색상 업데이트
function updateValueBadge(element, value, sensorType, fieldName) {
  element.className = "badge";

  const numValue = parseFloat(value);
  if (isNaN(numValue)) {
    element.classList.add("bg-secondary");
    return;
  }

  // 센서별 임계값 설정
  const thresholds = {
    PM: { "PM2.5": [15, 35, 75], PM10: [30, 80, 150] },
    O2: { 산소농도: [19, 21, 23] },
    MQ: { MQ값: [50, 100, 200] },
    NOX: { NO: [0.1, 0.2, 0.5], NO2: [0.1, 0.2, 0.5] },
    GASM: { 가스농도: [50, 100, 200] },
    WIND: { 풍속: [5, 10, 15] },
    VIBRO: { 진동: [0.5, 1.0, 2.0] },
    CRACK: { 균열폭: [0.1, 0.5, 1.0] },
    TILT: { 기울기: [1, 3, 5] },
    SOUND: { 소음: [40, 60, 80] },
  };

  let colorClass = "bg-success"; // 기본값: 양호

  // 임계값 확인
  const sensorThresholds = thresholds[sensorType];
  if (sensorThresholds) {
    for (const [key, values] of Object.entries(sensorThresholds)) {
      if (fieldName.includes(key) || fieldName.includes(key.substring(0, 2))) {
        if (numValue >= values[2]) {
          colorClass = "bg-danger";
        } else if (numValue >= values[1]) {
          colorClass = "bg-warning";
        } else if (numValue >= values[0]) {
          colorClass = "bg-primary";
        }
        break;
      }
    }
  }

  element.classList.add(colorClass);
}

// 상태 배지 업데이트
function updateStatusBadge(element, status) {
  // status가 undefined이거나 null인 경우 기본값 처리
  if (!status || status === "X") {
    element.style.color = "#0000FE"; // 기본 색상
    return;
  }

  const statusStr = String(status).toUpperCase(); // 문자열로 변환하고 대문자로

  // 정확한 값 매칭을 먼저 확인
  if (statusStr == "0.00" || statusStr == "0") {
    element.style.color = "#00f"; // 파란색 - 좋음
  } else if (statusStr == "1.00" || statusStr == "1") {
    element.style.color = "#2bc504";
  } else if (statusStr == "2.00" || statusStr == "2") {
    element.style.color = "#fb7d24";
  } else if (statusStr == "3.00" || statusStr == "3") {
    element.style.color = "#f00";
  } else if (
    statusStr.includes("G") ||
    statusStr.includes("0") ||
    statusStr.includes("좋음") ||
    statusStr.includes("GOOD")
  ) {
    element.style.color = "#00f"; // 파란색 - 좋음
  } else if (
    statusStr.includes("N") ||
    statusStr.includes("보통") ||
    statusStr.includes("NORMAL")
  ) {
    element.style.color = "#2bc504"; // 초록색 - 보통
  } else if (
    statusStr.includes("W") ||
    statusStr.includes("2") ||
    statusStr.includes("나쁨") ||
    statusStr.includes("BAD")
  ) {
    element.style.color = "#fb7d24"; // 주황색 - 나쁨
  } else if (
    statusStr.includes("D") ||
    statusStr.includes("3") ||
    statusStr.includes("매우나쁨") ||
    statusStr.includes("VERY BAD")
  ) {
    element.style.color = "#f00"; // 빨간색 - 매우나쁨
  } else {
    element.style.color = "#0000FE"; // 기본 파란색
  }
}

function showClock() {
  const currentDate = new Date();
  const currentTimeEl = document.getElementById("current-time");
  let msg = "";

  msg += currentDate.getFullYear() + "-";
  msg += (currentDate.getMonth() + 1).toString().padStart(2, "0") + "-";
  msg += currentDate.getDate().toString().padStart(2, "0") + "  ";
  msg += currentDate.getHours().toString().padStart(2, "0") + ":";
  msg += currentDate.getMinutes().toString().padStart(2, "0") + ":";
  msg += currentDate.getSeconds().toString().padStart(2, "0");
  currentTimeEl.innerText = msg;
  setTimeout(showClock, 1000);
}

// 이벤트 리스너
// window.addEventListener("load", toggleConnection);

// 센서 설정 로드 함수
async function loadSensorConfig() {
  try {
    addToLog("loadSensorConfig start", "warning");
    addToLog(`서버 URL:${SERVER_URL}`);
    addToLog(`API 키:${API_KEY}`);

    // API 키를 사용한 공개 엔드포인트 호출
    const response = await fetch(
      `${SERVER_URL}/api/public-sensor-config?api_key=${encodeURIComponent(
        API_KEY
      )}`
    );

    addToLog(
      `[디버그] response status: ${response.status}, ok: ${response.ok}`,
      "warning"
    );
    addToLog(`[디버그] response URL: ${response.url}`, "warning");

    if (response.ok) {
      const serverConfigs = await response.json();
      // 서버 설정을 우선 사용 (기본 설정과 합치지 않음)
      SENSOR_CONFIGS = serverConfigs;
      addToLog("[시스템] 서버에서 센서 설정을 로드했습니다.", "info");
      return true;
    } else if (response.status === 401) {
      addToLog("[경고] API 키 인증 실패 - 기본 설정을 사용합니다.", "warning");
      // 기본 설정 사용
      SENSOR_CONFIGS = {};
      return false;
    } else {
      addToLog(
        "[경고] 센서 설정 로드 실패 - 기본 설정을 사용합니다.",
        "warning"
      );
      // 기본 설정 사용
      SENSOR_CONFIGS = {};
      return false;
    }
  } catch (error) {
    addToLog(
      `[경고] 센서 설정 로드 중 오류 발생 - 기본 설정을 사용합니다. (서버: ${SERVER_URL})`,
      "warning"
    );
    addToLog(`[디버그] 오류 상세: ${error.message}`, "warning");
    // 기본 설정 사용
    SENSOR_CONFIGS = {};
    return false;
  }
}

// 연결 상태 모니터링 함수
let lastDataTime = null; // 마지막 데이터 수신 시간
function monitorConnection() {
  if (isConnected && lastDataTime) {
    const timeSinceLastData = Date.now() - lastDataTime;
    // 5분 이상 데이터가 없으면 경고
    if (timeSinceLastData > 300000) {
      // 5분 = 300,000ms
      addToLog("[경고] 5분 이상 데이터가 수신되지 않았습니다.", "warning");
      lastDataTime = null; // 중복 경고 방지
    }
  }
}

function setGridColumns(el, len) {
  if (len < 6) {
    if (len === 5) {
      el.style.setProperty("font-size", "40px");
      el.style.setProperty(
        "grid-template-columns",
        `repeat(3, minmax(auto, 1fr))`
      );
      el.style.setProperty(
        "grid-template-rows",
        `repeat(2, minmax(auto, ${(72 - 1.4) / 2}rem))`
      );
    } else {
      el.style.setProperty(
        "grid-template-columns",
        `repeat(${len}, minmax(auto, 1fr))`
      );
      el.style.setProperty("grid-template-rows", `repeat(1, 1fr)`);

      switch (len) {
        case 1:
          el.style.setProperty("font-size", "140px");
          break;
        case 2:
          el.style.setProperty("font-size", "90px");
          break;
        case 3:
          el.style.setProperty("font-size", "70px");
          break;
        case 4:
          el.style.setProperty("font-size", "50px");
          break;
        default:
          el.style.setProperty("font-size", "42px");
          break;
      }
    }
  } else if (len === 16) {
    el.style.setProperty("font-size", "35px");
    el.style.setProperty(
      "grid-template-columns",
      `repeat(4, minmax(auto, 1fr))`
    );
    el.style.setProperty(
      "grid-template-rows",
      `repeat(4, minmax(auto, ${(72 - 4.2) / 4}rem))`
    );
  } else {
    if (len / 5 <= 2) {
      if (len % 5 === 1) {
        el.style.setProperty(
          "grid-template-columns",
          "repeat(3, minmax(auto, 1fr))"
        );
        el.style.setProperty("font-size", "60px");
      } else if (len % 5 === 2 || len % 5 === 3) {
        el.style.setProperty(
          "grid-template-columns",
          "repeat(4, minmax(auto, 1fr))"
        );
        el.style.setProperty("font-size", "45px");
      } else {
        el.style.setProperty("font-size", "40px");
      }
      el.style.setProperty(
        "grid-template-rows",
        `repeat(2, minmax(auto, ${(72 - 1.4) / 2}rem))`
      );
    } else {
      if (len % 5 === 1) {
        el.style.setProperty(
          "grid-template-columns",
          "repeat(3, minmax(auto, 1fr))"
        );
        el.style.setProperty("font-size", "38px");
        el.style.setProperty(
          "grid-template-rows",
          `repeat(4, minmax(auto, ${(72 - 4.2) / 4}rem))`
        );
      } else if (len % 5 === 2) {
        el.style.setProperty(
          "grid-template-columns",
          "repeat(4, minmax(auto, 1fr))"
        );
        el.style.setProperty("font-size", "40px");
        el.style.setProperty(
          "grid-template-rows",
          `repeat(3, minmax(auto, ${(72 - 2.8) / 3}rem))`
        );
      } else if (len % 5 === 3 || len % 5 === 4) {
        el.style.setProperty(
          "grid-template-columns",
          "repeat(3, minmax(auto, 1fr))"
        );
        el.style.setProperty("font-size", "28px");
        el.style.setProperty(
          "grid-template-rows",
          `repeat(5, minmax(auto, ${(72 - 5.6) / 5}rem))`
        );
      } else {
        el.style.setProperty(
          "grid-template-columns",
          "repeat(5, minmax(auto, 1fr))"
        );
        el.style.setProperty("font-size", "35px");
        el.style.setProperty(
          "grid-template-rows",
          `repeat(3, minmax(auto, ${(72 - 2.8) / 3}rem))`
        );
      }
    }
  }
}

function gridSet() {
  const $wrap = document.getElementById("dynamic-layout");
  const $boxs = $wrap.querySelectorAll(".sensor-item");
  const length = $boxs.length;
  setGridColumns($wrap, length);
}

// 페이지 로드 시 초기화
window.addEventListener("load", async () => {
  try {
    // SQL.js 초기화
    await initSQLite();

    // 센서 설정 로드
    await loadSensorConfig();

    // DB 로드 완료 후 SSE 연결 시도
    const dbLoaded = await loadLocalDatabase();
    if (dbLoaded && csData.length > 0) {
      addToLog(`[시스템] ${csData.length}개 장비 정보 로드 완료`, "success");
      // toggleConnection() 제거하고 connectSSE() 직접 호출
      connectSSE();
    } else {
      addToLog("[경고] CS 테이블 데이터가 로드되지 않았습니다.", "warning");
    }

    // 시계 시작
    showClock();

    // 그리드 설정
    gridSet();

    // 30초마다 연결 상태 모니터링
    setInterval(monitorConnection, 30000);
  } catch (error) {
    addToLog(`[오류] 초기화 실패: ${error.message}`, "error");
    console.error("초기화 오류:", error);
  }
});

// 페이지 로드 시 초기화
document.addEventListener("DOMContentLoaded", async () => {
  // loadSettings();

  addToLog("[시스템] 실시간 센서 데이터 모니터가 준비되었습니다.", "info");

  // 센서 설정 로드 시도 (서버 없이도 작동하도록 개선)
  try {
    await loadSensorConfig();
  } catch (error) {
    addToLog(
      "[정보] 서버에 연결되지 않았습니다. 기본 설정으로 실행됩니다.",
      "info"
    );
    addToLog(
      "[정보] 센서 데이터를 받으려면 먼저 Flask 서버를 실행하세요.",
      "info"
    );
  }

  addToLog("[시스템] 설정 버튼을 클릭하여 서버 정보를 확인하세요.", "info");

  // 30초마다 연결 상태 모니터링
  setInterval(monitorConnection, 30000);
});

// 페이지 언로드 시 정리
window.addEventListener("beforeunload", () => {
  if (eventSource) {
    if (Array.isArray(eventSource)) {
      eventSource.forEach((source) => {
        if (source) source.close();
      });
    } else {
      eventSource.close();
    }
  }
});
