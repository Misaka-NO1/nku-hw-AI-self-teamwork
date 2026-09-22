/** 来源引用：显示来源与定位，不自动访问外部 URL。 */
export interface SourceRef {
  label: string;
  href?: string;
  verifiedAt?: string;
  locator?: string;
}
