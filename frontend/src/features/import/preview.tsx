import { createRoot } from "react-dom/client";
import { useState } from "react";
import ImportPage from "./ImportPage";
import TimetablePage from "../timetable/TimetablePage";
import type { TimetableImport } from "@campus/import-core";
function Preview(){const [timetable,setTimetable]=useState<TimetableImport|null>(null);return <><p style={{maxWidth:1200,margin:"20px auto"}}>本地导入核对预览：文件只在浏览器解析，不登录、不上传、不保存。日期由本次测试核对，不自动认定官方校历。</p><ImportPage datasetKind="personal" onPreview={setTimetable}/>{timetable && <TimetablePage timetable={timetable}/>}</>;}
createRoot(document.getElementById("root")!).render(<Preview/>);
