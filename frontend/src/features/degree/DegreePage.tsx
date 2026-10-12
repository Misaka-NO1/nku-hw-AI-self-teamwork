import { ReaderInstallGuide } from '../../components/ReaderInstallGuide';
/** Compatibility for old links; review and saving happen in Agent. */
export function DegreePage() {
  const agentUrl = import.meta.env.VITE_GENIOS_AGENT_URL as string | undefined;
  return <section>
    <h2>在 Agent 中导入培养计划</h2>
    <ol>
      <li>在教务“计划完成情况”页面，用课表共用拓展导出 degree-progress.json。</li>
      <li>把 JSON 发给南开 Agent，请它核对各分类学分。</li>
      <li>核对后回复“确认保存这份学分报告”。保存成功后，可在对话中查询进度。</li>
    </ol>
    <p>只保存总览、分类学分与状态，不保存课程成绩、姓名或学号。未确认不会覆盖旧报告。</p>
    {agentUrl ? <a href={agentUrl}>打开南开 Agent →</a> : <p>请回到学校平台的南开校园助手对话。</p>}
    <ReaderInstallGuide />
  </section>;
}
