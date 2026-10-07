// NK-GeniOS code node. Only the reviewed public manifest snapshot; no URLs, SQL or identity inputs.
function handler(params) {
  const manifest = [{"id":"study-s1-calculus-6e53f8532c216ccc","course":"y1-s1-calculus","version":"sha256:6e53f8532c216ccc6874fc9a3248c796665f8ba34c16242929591963e2fb6cdd"},{"id":"study-s1-ideology-e834581c52ce1f41","course":"y1-s1-ideology","version":"sha256:e834581c52ce1f41575d911c0b2105b1ee2a710ee700723e2020ec26050535af"},{"id":"study-s1-ideology-8a05a12b1b8a7e09","course":"y1-s1-ideology","version":"sha256:8a05a12b1b8a7e09fdc98e10a94b62ef9d844624bb12c1b901907540c2d7e57c"},{"id":"study-s1-ideology-2146cd59f5c57d41","course":"y1-s1-ideology","version":"sha256:2146cd59f5c57d412a536bf723ac152e60d9a0f9493a116fcbbc38d5caed1e19"},{"id":"study-s1-linear-algebra-f79a31b39bd88215","course":"y1-s1-linear-algebra","version":"sha256:f79a31b39bd88215e5c15e8928f1b3a14c77e123dc8783344cb8a38f88b78bbe"},{"id":"study-s1-programming-26355822c1f8144c","course":"y1-s1-programming","version":"sha256:26355822c1f8144c44853b5794e683535ccf851459c1d41bb4191ce2c317b39b"},{"id":"study-s1-programming-b8a8c17240ffa3e4","course":"y1-s1-programming","version":"sha256:b8a8c17240ffa3e480bb97cdaabd683e5e9ea21451976f5f3fdbe8a089fb4363"},{"id":"study-s2-calculus-90f6102c4992a3c7","course":"y1-s2-calculus","version":"sha256:90f6102c4992a3c7b131bd362fa755016a29f554a09b3075b926562109c91ec2"},{"id":"study-s2-calculus-0b11b3601df78a74","course":"y1-s2-calculus","version":"sha256:0b11b3601df78a74eb154ca53a7238dd50f465e7623ddf12d16a9d5a333e8cef"},{"id":"study-s2-marxism-0a0bec651848beaf","course":"y1-s2-marxism","version":"sha256:0a0bec651848beafc42a415b224c43e1dbd5d9d1ff26e249bd7db804eaa2f86d"},{"id":"study-s2-marxism-28315c18c093abf3","course":"y1-s2-marxism","version":"sha256:28315c18c093abf30cfb57975d81364179d137a301954d8dfc62f900cf62f201"},{"id":"study-s2-marxism-9ecf25ff0629bcad","course":"y1-s2-marxism","version":"sha256:9ecf25ff0629bcad1c2af58c7820d3da7fd1abf466676296c0e675bb50b59ffe"},{"id":"study-s2-marxism-19de0432715b4aa5","course":"y1-s2-marxism","version":"sha256:19de0432715b4aa5054d864ebdb7575acb17cc131b2132e4224da7f363ce78b2"},{"id":"study-s2-marxism-88a5a68d925b7f84","course":"y1-s2-marxism","version":"sha256:88a5a68d925b7f84527d474b0fa3e913ec49af739be8e188d81162fe731801f3"},{"id":"study-s2-marxism-80159e7fae0c909f","course":"y1-s2-marxism","version":"sha256:80159e7fae0c909ffbc56f7caa11a48362967abddd1cbe65ae7de6d6c4b163f7"},{"id":"study-s2-physics-c6b936374c8ae864","course":"y1-s2-physics","version":"sha256:c6b936374c8ae8643d6f217888b673eaca884fac3a5980dc7145c74a746a5fa6"},{"id":"study-s2-physics-cb6c50ee1df79476","course":"y1-s2-physics","version":"sha256:cb6c50ee1df79476f9d6d24f7301600cd351d99927dcc9997ec21fef7da27902"},{"id":"study-s2-physics-0a46c38726e23c48","course":"y1-s2-physics","version":"sha256:0a46c38726e23c48cc58f4b2ebc93b0c121cb63a40c62d9b6c1b4585955fc2dd"},{"id":"study-s2-physics-b91d080a8c79df85","course":"y1-s2-physics","version":"sha256:b91d080a8c79df85a2be05f2eee8cdee0f24841c64f072c7d573030b504fdf92"},{"id":"study-s2-physics-efbde7e09544ed14","course":"y1-s2-physics","version":"sha256:efbde7e09544ed1453cb4810091d879cd516e5480ff80867a890c5235900b5bc"},{"id":"study-s2-physics-46bbcebfd699f638","course":"y1-s2-physics","version":"sha256:46bbcebfd699f638b035811f084fa541118b059bd4d9548bac67d82e3d9a883c"},{"id":"study-s2-physics-2329b12e32d546f8","course":"y1-s2-physics","version":"sha256:2329b12e32d546f8876e82f465c3937a29ff474328c806c6e3db61fc2d677768"},{"id":"study-s2-probability-5f5e607db31aada8","course":"y1-s2-probability","version":"sha256:5f5e607db31aada887e24361ddbfe184ed15fba55fb2736d4d4510b539a52583"},{"id":"study-s2-probability-d5f582f9efde68b4","course":"y1-s2-probability","version":"sha256:d5f582f9efde68b49c60a0f5da0a0fcafd6d14137f4052155f2134451de152e7"},{"id":"study-s2-probability-451d99011df209b5","course":"y1-s2-probability","version":"sha256:451d99011df209b5a08cdafd05cbd4f94a43af021f33a631788a3408d8e1f2e7"},{"id":"study-s2-probability-101feb5a6eaba5dd","course":"y1-s2-probability","version":"sha256:101feb5a6eaba5ddae0108f30346630bdd5a6f82dbff78f6af1064d1c97915be"},{"id":"study-s2-probability-a7dfaf2beb4f155f","course":"y1-s2-probability","version":"sha256:a7dfaf2beb4f155f2c5c292a4b09e5eb5cd46c3a171e4902f660d5df747d62ca"},{"id":"study-s2-probability-1334b535ee83c23e","course":"y1-s2-probability","version":"sha256:1334b535ee83c23eafa93a9fb984744d6bb201c804fa5dad5a332cc04e2b3ba2"},{"id":"study-s2-programming-ecb1b840316f954b","course":"y1-s2-programming","version":"sha256:ecb1b840316f954b8d9a997430192621ee40901136caea95714050b86957e8ca"},{"id":"study-s2-programming-69542effd80181aa","course":"y1-s2-programming","version":"sha256:69542effd80181aaad6fb69c491380107655b11c28e7e2a01f54cbbfe83f39b7"},{"id":"study-s2-programming-f076c553a310a022","course":"y1-s2-programming","version":"sha256:f076c553a310a02215ab24cc3cbaae9e6bbc764cf9b2bba07326450d9e4c8316"},{"id":"study-s2-programming-efb6bb2d624c4062","course":"y1-s2-programming","version":"sha256:efb6bb2d624c4062d4e00c6267b2ad7e9c414926222cad1589270f36f9cef5a4"},{"id":"study-s2-programming-cd29346f86e832fa","course":"y1-s2-programming","version":"sha256:cd29346f86e832fa017f1d395328aedcbbdbccb5a706c69e63b54508d7a0155e"}];
  const courses = [...new Set(manifest.map(row => row.course))];
  if (!params || typeof params.course_id !== "string" || typeof params.question !== "string"
      || params.question.length < 1 || params.question.length > 1024 || !Array.isArray(params.outputList)
      || params.outputList.length > 20) throw new Error("INVALID_STUDY_INPUT");
  const question = params.question;
  const materialId = params.material_id === undefined || params.material_id === null ? "" : params.material_id;
  if (typeof materialId !== "string" || materialId.length > 100) throw new Error("INVALID_STUDY_INPUT");
  if (!courses.includes(params.course_id)) {
    return {status: "unknown_course", context: "", sources_json: "[]", question, data_version: "y1-070600fb47f92e70"};
  }
  if (materialId && !manifest.some(row => row.id === materialId && row.course === params.course_id)) {
    return {status: "unknown_material", context: "", sources_json: "[]", question, data_version: "y1-070600fb47f92e70"};
  }
  const selected = [];
  const sources = [];
  const seen = new Set();
  function field(text, name) {
    // NK-GeniOS turns Markdown metadata lines into one paragraph. Preserve exact
    // values and conflicting-field rejection for both line and inline layouts.
    const keys = "material_id|version|course_id|chunk_id|source_label|page_label|source_excerpt_ref|extraction_method|quality_warning";
    const pattern = new RegExp("(?:^|[ \\t])" + name + ":[ \\t]*([^\\r\\n]*?)(?=[ \\t]+(?:" + keys + "):|[\\r\\n]|$)", "gm");
    const values = [...text.matchAll(pattern)].map(match => match[1].trim());
    const unique = [...new Set(values)];
    return unique.length === 1 ? unique[0] : null;
  }
  for (const item of params.outputList) {
    if (!item || typeof item.output !== "string" || item.output.length > 20000) continue;
    const text = item.output.replace(/\\_/g, "_");
    const id = field(text, "material_id");
    const row = manifest.find(entry => entry.id === id && entry.course === params.course_id && (!materialId || entry.id === materialId));
    if (!row || field(text, "course_id") !== row.course || field(text, "version") !== row.version) continue;
    const pageLabel = field(text, "page_label");
    const match = pageLabel && /^PDF 第 ([1-9][0-9]{0,3}) 页$/.exec(pageLabel);
    if (!match) continue; // No page/body header: index only, not answer evidence.
    const page = Number(match[1]);
    const expected = "knowledge/study/sources/year1/pdf/" + row.id + ".pdf#page=" + page;
    if (field(text, "source_excerpt_ref") !== expected) continue;
    const chunk = field(text, "chunk_id");
    if (!chunk || !chunk.startsWith(row.id + "-p" + String(page).padStart(4, "0") + "-c")) continue;
    if (seen.has(chunk)) continue;
    const name = item.metadata && item.metadata.document_name;
    if (name !== row.id + ".md") continue;
    seen.add(chunk);
    const source = {material_id: row.id, course_id: row.course, version: row.version,
      chunk_id: chunk, page, file_name: name, source_label: field(text, "source_label"),
      quality_warning: "提取/OCR尚未逐页人工核对，公式、代码、图表对照原PDF；历史资料不是当前考试范围。"};
    sources.push(source);
    selected.push({source, excerpt: text});
  }
  return {status: sources.length ? "grounded" : "no_matching_body",
    context: JSON.stringify(selected), sources_json: JSON.stringify(sources), question, data_version: "y1-070600fb47f92e70"};
}
