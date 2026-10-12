export const READER_VERSION = '0.3.4';
export const READER_DOWNLOAD = `/assets/campus-reader-${READER_VERSION}.zip`;

/** One desktop reader for both EAMIS pages; installation never grants data access. */
export function ReaderInstallGuide() {
  return <section aria-label="共用拓展安装步骤">
    <p><a href={READER_DOWNLOAD} download>下载课表与培养计划共用拓展 v{READER_VERSION}（Chrome / Edge）</a></p>
    <h3>安装方法</h3>
    <ol>
      <li>在电脑上下载 ZIP，解压到一个固定文件夹，不要直接选择 ZIP。</li>
      <li>在 Chrome 地址栏输入 <code>chrome://extensions</code>；Edge 输入 <code>edge://extensions</code>。</li>
      <li>打开“开发者模式”，点击“加载已解压的扩展程序”，选择包含 <code>manifest.json</code> 的文件夹。</li>
      <li>核对名称“南开校园助手 · 教务课表与培养计划”和版本 {READER_VERSION}。更新时停用或移除旧版，只保留这一份共用拓展。</li>
      <li>刷新已经打开的教务页面：课表页点“读取并导入课表”；“计划完成情况”页点“导出计划完成情况 JSON”。</li>
    </ol>
    <p>拓展不会自动采集或保存。培养计划导出的 degree-progress.json 发给 Agent，核对并明确确认后才保存。</p>
    <p>手机和内置浏览器不能安装此电脑拓展；可在电脑导出 JSON，再用手机上传。课表文件在工具站“导入课表”页面导入，学分文件发给 Agent。</p>
  </section>;
}
