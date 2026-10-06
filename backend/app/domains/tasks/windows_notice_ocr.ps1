param([Parameter(Mandatory=$true)][string]$ImagePath)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
try {
    $ocrStage = 'runtime'
    Add-Type -AssemblyName System.Runtime.WindowsRuntime
    [Windows.Storage.StorageFile,Windows.Storage,ContentType=WindowsRuntime] | Out-Null
    [Windows.Storage.FileAccessMode,Windows.Storage,ContentType=WindowsRuntime] | Out-Null
    [Windows.Storage.Streams.IRandomAccessStream,Windows.Storage.Streams,ContentType=WindowsRuntime] | Out-Null
    [Windows.Graphics.Imaging.BitmapDecoder,Windows.Graphics.Imaging,ContentType=WindowsRuntime] | Out-Null
    [Windows.Graphics.Imaging.SoftwareBitmap,Windows.Graphics.Imaging,ContentType=WindowsRuntime] | Out-Null
    [Windows.Media.Ocr.OcrEngine,Windows.Media.Ocr,ContentType=WindowsRuntime] | Out-Null
    [Windows.Media.Ocr.OcrResult,Windows.Media.Ocr,ContentType=WindowsRuntime] | Out-Null
    $taskMethod = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
        $_.Name -eq 'AsTask' -and $_.IsGenericMethod -and $_.GetParameters().Count -eq 1 -and
        $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
    } | Select-Object -First 1
    function Await-OcrOperation($Operation, $ResultType) {
        $operationTask = $taskMethod.MakeGenericMethod($ResultType).Invoke($null, @($Operation))
        $operationTask.Wait()
        $operationTask.Result
    }
    $ocrStage = 'file'
    $imageFile = Await-OcrOperation ([Windows.Storage.StorageFile]::GetFileFromPathAsync($ImagePath)) ([Windows.Storage.StorageFile])
    $imageStream = Await-OcrOperation ($imageFile.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
    try {
        $ocrStage = 'bitmap'
        $decoder = Await-OcrOperation ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($imageStream)) ([Windows.Graphics.Imaging.BitmapDecoder])
        $bitmap = Await-OcrOperation ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
        $ocrStage = 'language'
        $language = [Windows.Media.Ocr.OcrEngine]::AvailableRecognizerLanguages | Where-Object { $_.LanguageTag -match '^zh' } | Select-Object -First 1
        if ($null -eq $language) { throw 'Chinese recognizer unavailable' }
        $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage($language)
        $ocrStage = 'recognize'
        $recognized = Await-OcrOperation ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
        @{ text = $recognized.Text } | ConvertTo-Json -Compress
    } finally { $imageStream.Dispose() }
} catch {
    # Never print original paths, document text or engine exception details.
    [Console]::Error.WriteLine('NOTICE_OCR_FAILED:' + $ocrStage + ':' + $_.Exception.GetType().Name)
    exit 1
}
