import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { AnalyzeRequest, AnalysisResponse } from '../models/emotion.models';

@Injectable({ providedIn: 'root' })
export class EmotionService {
  private readonly API_URL = 'http://localhost:8000';

  constructor(private http: HttpClient) {}

  analyze(request: AnalyzeRequest): Observable<AnalysisResponse> {
    return this.http.post<AnalysisResponse>(
      `${this.API_URL}/analyze`,
      request
    );
  }

  healthCheck(): Observable<unknown> {
    return this.http.get(`${this.API_URL}/health`);
  }
}
