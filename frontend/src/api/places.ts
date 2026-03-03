import apiClient from './client';

export interface CampaignBrief {
  campaign_id: number;
  campaign_type: string;
  status: string;
  total_limit: number | null;
  start_date: string;
  end_date: string;
}

export interface PlaceRecommendation {
  place_id: number;
  is_existing: boolean;
  existing_campaigns: CampaignBrief[];
  recommended_network: string | null;
  recommended_action: 'new' | 'extend';
}

export interface TypeRecommendation {
  campaign_type: string;
  is_existing: boolean;
  existing_campaigns: CampaignBrief[];
  recommended_network: string | null;
  recommended_action: 'new' | 'extend';
  available_networks: number;
}

export interface PlaceRecommendationV2 {
  place_id: number;
  is_existing: boolean;
  recommended_campaign_type: 'traffic' | 'save';
  recommendation_reason: string;
  traffic: TypeRecommendation;
  save: TypeRecommendation;
}

export const placesApi = {
  recommend: async (params: {
    place_url: string;
    company_id: number;
    campaign_type?: string;
  }): Promise<PlaceRecommendation> => {
    const response = await apiClient.get<PlaceRecommendation>('/places/recommend', { params });
    return response.data;
  },

  recommendBoth: async (params: {
    place_url: string;
    company_id: number;
  }): Promise<PlaceRecommendationV2> => {
    const response = await apiClient.get<PlaceRecommendationV2>('/places/recommend', { params });
    return response.data;
  },
};
