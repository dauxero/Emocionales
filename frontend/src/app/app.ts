import { Component, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { EmotionService } from './services/emotion.service';
import {
  AnalysisResponse,
  AGE_RANGES,
  CONTEXT_OPTIONS,
  SelectOption,
} from './models/emotion.models';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './app.html',
  styleUrl: './app.css',
})
export class App {
  // ── State ──
  text = '';
  selectedAge: string | null = null;
  selectedContext: string | null = null;
  loading = false;
  result: AnalysisResponse | null = null;
  error: string | null = null;
  showRisks = false;

  // ── Options ──
  ageRanges: SelectOption[] = AGE_RANGES;
  contextOptions: SelectOption[] = CONTEXT_OPTIONS;

  constructor(
    private emotionService: EmotionService,
    private cdr: ChangeDetectorRef,
  ) {}

  get canSubmit(): boolean {
    return this.text.trim().length >= 3 && !this.loading;
  }

  get alertColorClass(): string {
    if (!this.result) return '';
    switch (this.result.alert_level) {
      case 'Rojo':  return 'alert-red';
      case 'Ámbar': return 'alert-amber';
      case 'Verde': return 'alert-green';
      default:      return 'alert-green';
    }
  }

  get intensityBarWidth(): string {
    if (!this.result) return '0%';
    return `${(this.result.dominant_emotion.score * 100).toFixed(0)}%`;
  }

  onSubmit(): void {
    if (!this.canSubmit) return;

    this.loading = true;
    this.error = null;
    this.result = null;

    this.emotionService
      .analyze({
        text: this.text.trim(),
        student_age_range: this.selectedAge,
        context: this.selectedContext,
      })
      .subscribe({
        next: (res) => {
          this.result = res;
          this.loading = false;
          this.cdr.markForCheck();
        },
        error: (err) => {
          this.error =
            err.status === 0
              ? 'No se pudo conectar con el servidor. ¿Está corriendo el backend en localhost:8000?'
              : err.error?.detail || 'Ocurrió un error inesperado.';
          this.loading = false;
          this.cdr.markForCheck();
        },
      });
  }

  resetForm(): void {
    this.result = null;
    this.error = null;
    this.text = '';
    this.showRisks = false;
  }

  toggleRisks(): void {
    this.showRisks = !this.showRisks;
  }

  getRiskBarColor(risk: { label: string; score: number; is_school_related: boolean }): string {
    if (risk.score >= 0.6) return 'var(--red)';
    if (risk.score >= 0.35) return 'var(--amber)';
    return 'var(--green)';
  }
}
